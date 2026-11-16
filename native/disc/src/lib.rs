//! Bounded GameCube ISO/GCM/RVZ conversion through a pinned nod library.
use std::ffi::{CStr, c_char};
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::path::{Path, PathBuf};
use std::ptr;

use nod::common::{Compression, Format};
use nod::read::{DiscOptions, DiscReader, PartitionEncryption};
use nod::write::{DiscWriter, ProcessOptions, ScrubLevel};

const MAX_DISC_SIZE: u64 = 1_459_978_240;
const CANCELLED: &str = "conversion cancelled";
type Progress = Option<extern "C" fn(u64, u64) -> i32>;

struct Output {
    file: Option<File>,
    path: PathBuf,
    complete: bool,
}

impl Output {
    fn new(path: &Path) -> io::Result<Self> {
        Ok(Self {
            file: Some(OpenOptions::new().write(true).create_new(true).open(path)?),
            path: path.to_owned(),
            complete: false,
        })
    }
    fn file(&mut self) -> &mut File {
        self.file.as_mut().expect("owned output is open")
    }
}

impl Drop for Output {
    fn drop(&mut self) {
        self.file.take();
        if !self.complete {
            let _ = std::fs::remove_file(&self.path);
        }
    }
}

fn notify(callback: Progress, done: u64, total: u64) -> io::Result<()> {
    if callback.is_some_and(|function| function(done, total) != 0) {
        Err(io::Error::new(io::ErrorKind::Interrupted, CANCELLED))
    } else {
        Ok(())
    }
}

fn convert(source: &Path, destination: &Path, rvz: bool, callback: Progress) -> Result<(), String> {
    notify(callback, 0, 1).map_err(|e| e.to_string())?;
    let threads = std::thread::available_parallelism().map_or(1, |n| n.get().min(4));
    let options = DiscOptions {
        partition_encryption: PartitionEncryption::Original,
        preloader_threads: threads.min(2),
    };
    let mut disc = DiscReader::new(source, &options).map_err(|e| e.to_string())?;
    let size = disc.disc_size();
    if !(0x440..=MAX_DISC_SIZE).contains(&size) {
        return Err("unsupported disc size".into());
    }
    let mut header = [0_u8; 0x20];
    disc.read_exact(&mut header).map_err(|e| e.to_string())?;
    if header[0x1c..] != [0xc2, 0x33, 0x9f, 0x3d] {
        return Err("not a GameCube disc".into());
    }
    disc.seek(SeekFrom::Start(0)).map_err(|e| e.to_string())?;
    notify(callback, 0, size).map_err(|e| e.to_string())?;
    let mut output = Output::new(destination).map_err(|e| e.to_string())?;
    if rvz {
        let format = nod::write::FormatOptions {
            format: Format::Rvz,
            compression: Compression::Zstandard(5),
            block_size: 131_072,
        };
        let writer = DiscWriter::new(disc, &format).map_err(|e| e.to_string())?;
        let processing = ProcessOptions {
            processor_threads: threads,
            scrub: ScrubLevel::None,
            digest_crc32: true,
            ..Default::default()
        };
        let finalization = writer
            .process(
                |data, done, total| {
                    notify(callback, done, total)?;
                    output.file().write_all(data.as_ref())
                },
                &processing,
            )
            .map_err(|e| e.to_string())?;
        if !finalization.header.is_empty() {
            output.file().rewind().map_err(|e| e.to_string())?;
            output
                .file()
                .write_all(finalization.header.as_ref())
                .map_err(|e| e.to_string())?;
        }
    } else {
        let mut buffer = vec![0_u8; 1024 * 1024];
        let mut done = 0;
        while done < size {
            notify(callback, done, size).map_err(|e| e.to_string())?;
            let amount = buffer.len().min((size - done) as usize);
            disc.read_exact(&mut buffer[..amount])
                .map_err(|e| e.to_string())?;
            output
                .file()
                .write_all(&buffer[..amount])
                .map_err(|e| e.to_string())?;
            done += amount as u64;
        }
    }
    output.file().flush().map_err(|e| e.to_string())?;
    output.file().sync_all().map_err(|e| e.to_string())?;
    notify(callback, size, size).map_err(|e| e.to_string())?;
    output.complete = true;
    Ok(())
}

unsafe fn error_message(output: *mut u8, capacity: usize, message: &str) {
    if output.is_null() || capacity == 0 {
        return;
    }
    let length = message.len().min(capacity - 1);
    unsafe {
        ptr::copy_nonoverlapping(message.as_ptr(), output, length);
        output.add(length).write(0);
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn orre_disc_abi_version() -> u32 {
    1
}

/// Paths and the output error buffer are borrowed only for this call.
/// Returns 0 on success, 1 on cancellation, 2 on input/I/O error, 3 on panic.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn orre_disc_convert(
    source: *const c_char,
    destination: *const c_char,
    rvz: i32,
    callback: Progress,
    error: *mut u8,
    error_capacity: usize,
) -> i32 {
    let result = catch_unwind(AssertUnwindSafe(|| -> Result<(), String> {
        if source.is_null() || destination.is_null() || !matches!(rvz, 0 | 1) {
            return Err("invalid conversion arguments".into());
        }
        let input = unsafe { CStr::from_ptr(source) }
            .to_str()
            .map_err(|_| "invalid UTF-8 input path")?;
        let output = unsafe { CStr::from_ptr(destination) }
            .to_str()
            .map_err(|_| "invalid UTF-8 output path")?;
        convert(Path::new(input), Path::new(output), rvz == 1, callback)
    }));
    match result {
        Ok(Ok(())) => 0,
        Ok(Err(message)) => {
            let cancelled = message.contains(CANCELLED);
            unsafe {
                error_message(error, error_capacity, &message);
            }
            if cancelled { 1 } else { 2 }
        }
        Err(_) => {
            unsafe {
                error_message(error, error_capacity, "disc conversion failed internally");
            }
            3
        }
    }
}
