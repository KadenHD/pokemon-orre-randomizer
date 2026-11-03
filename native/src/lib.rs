//! Bit-identical implementation of the project's reference GameCube LZSS codec.
use std::collections::{HashMap, VecDeque};

pub fn compress(data: &[u8]) -> Vec<u8> {
    compress_cancellable(data, || false).expect("uncancellable encoder")
}

fn compress_cancellable(data: &[u8], mut cancelled: impl FnMut() -> bool) -> Option<Vec<u8>> {
    let mut positions: HashMap<[u8; 3], VecDeque<usize>> = HashMap::new();
    let mut output = vec![0; 16];
    let mut pos = 0;
    let mut next_check = 0;
    while pos < data.len() {
        if pos >= next_check {
            if cancelled() { return None; }
            next_check = pos.saturating_add(16 * 1024);
        }
        let flag_pos = output.len();
        output.push(0);
        let mut flags = 0;
        for bit in 0..8 {
            if pos == data.len() { break; }
            let (mut length, mut candidate) = (0, 0);
            let maximum = 18.min(data.len() - pos);
            if maximum >= 3 {
                let key = [data[pos], data[pos + 1], data[pos + 2]];
                let matches = positions.entry(key).or_default();
                while matches.front().is_some_and(|&p| p + 4096 < pos) { matches.pop_front(); }
                for &previous in matches.iter().rev().take(128) {
                    let mut matched = 3;
                    while matched < maximum && data[previous + matched] == data[pos + matched] {
                        matched += 1;
                    }
                    if matched > length {
                        (length, candidate) = (matched, previous);
                        if length == maximum { break; }
                    }
                }
            }
            if length >= 3 {
                let ring = (0xfee + candidate) & 0xfff;
                output.push((ring & 0xff) as u8);
                output.push((((ring >> 4) & 0xf0) | (length - 3)) as u8);
            } else {
                length = 1;
                flags |= 1 << bit;
                output.push(data[pos]);
            }
            for consumed in pos..pos + length {
                if consumed + 3 <= data.len() {
                    let key = [data[consumed], data[consumed + 1], data[consumed + 2]];
                    let queue = positions.entry(key).or_default();
                    while queue.front().is_some_and(|&p| p + 4096 < consumed) { queue.pop_front(); }
                    queue.push_back(consumed);
                }
            }
            pos += length;
        }
        output[flag_pos] = flags;
    }
    let stored = output.len() as u32;
    output[0..4].copy_from_slice(b"LZSS");
    output[4..8].copy_from_slice(&(data.len() as u32).to_be_bytes());
    output[8..12].copy_from_slice(&stored.to_be_bytes());
    if cancelled() { None } else { Some(output) }
}

pub fn decompress(data: &[u8], capacity: usize) -> Option<Vec<u8>> {
    if data.len() < 16 || &data[..4] != b"LZSS" { return None; }
    let expected = u32::from_be_bytes(data[4..8].try_into().ok()?) as usize;
    let stored = u32::from_be_bytes(data[8..12].try_into().ok()?) as usize;
    if stored != data.len() || expected > capacity { return None; }
    let mut ring = [0u8; 4096];
    let (mut cursor, mut pos) = (0xfee, 16);
    let mut output = Vec::with_capacity(expected);
    while output.len() < expected {
        let flags = *data.get(pos)?;
        pos += 1;
        for bit in 0..8 {
            if output.len() == expected { break; }
            if flags & (1 << bit) != 0 {
                let value = *data.get(pos)?;
                pos += 1;
                output.push(value);
                ring[cursor] = value;
                cursor = (cursor + 1) & 0xfff;
            } else {
                let a = *data.get(pos)? as usize;
                let b = *data.get(pos + 1)? as usize;
                pos += 2;
                let source = a | ((b & 0xf0) << 4);
                let length = (b & 0xf) + 3;
                if output.len() + length > expected { return None; }
                for k in 0..length {
                    let value = ring[(source + k) & 0xfff];
                    output.push(value);
                    ring[cursor] = value;
                    cursor = (cursor + 1) & 0xfff;
                }
            }
        }
    }
    if pos == stored { Some(output) } else { None }
}

#[unsafe(no_mangle)]
pub extern "C" fn colosseum_codec_version() -> u32 { 1 }

/// # Safety
/// Input must address `len` readable bytes, output `capacity` writable bytes.
/// Buffers must not overlap. They remain owned by the caller.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn colosseum_compress(input: *const u8, len: usize,
                                          output: *mut u8, capacity: usize) -> isize {
    if input.is_null() || output.is_null() || len > u32::MAX as usize { return -1; }
    let data = unsafe { std::slice::from_raw_parts(input, len) };
    let encoded = compress(data);
    if encoded.len() > capacity { return -1; }
    unsafe { std::ptr::copy_nonoverlapping(encoded.as_ptr(), output, encoded.len()); }
    encoded.len() as isize
}

/// # Safety
/// Same buffers as `colosseum_compress`; `cancelled`, when provided, must remain
/// callable until return. It runs synchronously on this caller's thread. A
/// nonzero callback result cancels without writing any bytes to `output`.
/// Returns -2 for cancellation and -1 for invalid arguments/capacity.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn colosseum_compress_cancellable(
    input: *const u8, len: usize, output: *mut u8, capacity: usize,
    cancelled: Option<extern "C" fn() -> i32>,
) -> isize {
    if input.is_null() || output.is_null() || len > u32::MAX as usize { return -1; }
    let data = unsafe { std::slice::from_raw_parts(input, len) };
    let Some(encoded) = compress_cancellable(data, || cancelled.is_some_and(|call| call() != 0))
        else { return -2; };
    if encoded.len() > capacity { return -1; }
    unsafe { std::ptr::copy_nonoverlapping(encoded.as_ptr(), output, encoded.len()); }
    encoded.len() as isize
}

/// # Safety
/// Same buffer ownership and validity requirements as `colosseum_compress`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn colosseum_decompress(input: *const u8, len: usize,
                                            output: *mut u8, capacity: usize) -> isize {
    if input.is_null() || output.is_null() { return -1; }
    let data = unsafe { std::slice::from_raw_parts(input, len) };
    match decompress(data, capacity) {
        Some(decoded) => {
            unsafe { std::ptr::copy_nonoverlapping(decoded.as_ptr(), output, decoded.len()); }
            decoded.len() as isize
        }
        None => -1,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn literals_and_overlapping_roundtrip() {
        assert_eq!(&compress(b"abc")[16..], b"\x07abc");
        for raw in [vec![], vec![0; 20000], vec![b'A'; 12000], b"abc".repeat(6000),
                    (0..20000).map(|i| (i % 256) as u8).collect()] {
            assert_eq!(decompress(&compress(&raw), raw.len()), Some(raw));
        }
    }
    #[test]
    fn corruption_and_bounds() {
        let valid = compress(b"abcabcabc");
        assert_eq!(decompress(&valid, 2), None);
        for len in 0..valid.len() { assert_eq!(decompress(&valid[..len], 100), None); }
        let mut trailing = valid.clone(); trailing.push(0);
        assert_eq!(decompress(&trailing, 100), None);
        let mut overrun = valid; overrun[4..8].copy_from_slice(&4u32.to_be_bytes());
        assert_eq!(decompress(&overrun, 100), None);
    }
    #[test]
    fn ffi_rejects_invalid_pointers_and_small_buffers() {
        let mut buffer = [0u8; 8];
        unsafe {
            assert_eq!(colosseum_compress(std::ptr::null(), 0, buffer.as_mut_ptr(), 8), -1);
            assert_eq!(colosseum_compress(b"abc".as_ptr(), 3, buffer.as_mut_ptr(), 8), -1);
        }
    }
    #[test]
    fn cooperative_cancellation_never_publishes_partial_output() {
        let data = vec![b'A'; 128 * 1024];
        let mut calls = 0;
        assert!(compress_cancellable(&data, || { calls += 1; calls == 3 }).is_none());
        assert_eq!(calls, 3);
        assert_eq!(compress_cancellable(&data, || false), Some(compress(&data)));
        extern "C" fn stop() -> i32 { 1 }
        let mut buffer = vec![0x55u8; data.len() + data.len() / 8 + 16];
        unsafe {
            assert_eq!(colosseum_compress_cancellable(data.as_ptr(), data.len(),
                buffer.as_mut_ptr(), buffer.len(), Some(stop)), -2);
        }
        assert!(buffer.iter().all(|&value| value == 0x55));
    }
}
