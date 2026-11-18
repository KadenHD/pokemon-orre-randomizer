#include <stdlib.h>
#include "musyx/pc.h"
#include <string.h>
#include "musyx/dspvoice.h"

__declspec(dllexport) unsigned orre_music_abi_version(void) { return 1; }

/* Generic Nintendo DSP ADPCM decoder. Inputs are host-validated stream fields;
 * coefficients are signed host-endian values. No game format or resource is
 * compiled into this function. Output is interleaved stereo PCM16. */
__declspec(dllexport) int orre_decode_dsp(const unsigned char* body, size_t body_size,
    const short* coefficients, unsigned frames, unsigned channels,
    unsigned interleave, short* output, size_t output_samples) {
    if (!body || !coefficients || !output || !frames || channels < 1 || channels > 2 ||
        interleave < 8 || interleave % 8 || interleave > 1048576 ||
        frames > 33554432 || output_samples < (size_t)frames * 2) return 0;
    for (unsigned channel = 0; channel < channels; ++channel) {
        int first = 0, second = 0;
        unsigned written = 0;
        for (size_t block = 0; block < body_size && written < frames;
             block += (size_t)interleave * channels) {
            size_t begin = block + (size_t)channel * interleave;
            size_t end = begin + interleave;
            if (end > body_size) end = body_size;
            for (size_t offset = begin; offset + 8 <= end && written < frames; offset += 8) {
                unsigned control = body[offset], predictor = control >> 4;
                if (predictor >= 8) return 0;
                int scale = 1 << (control & 15);
                int a1 = coefficients[channel * 16 + predictor * 2];
                int a2 = coefficients[channel * 16 + predictor * 2 + 1];
                for (unsigned nibble_index = 0; nibble_index < 14 && written < frames; ++nibble_index) {
                    unsigned byte = body[offset + 1 + nibble_index / 2];
                    int nibble = (nibble_index & 1) ? byte & 15 : byte >> 4;
                    if (nibble & 8) nibble -= 16;
                    /* Signed division would truncate toward zero; DSP uses
                     * arithmetic right shift, which MSVC implements here. */
                    long long accumulator = (long long)nibble * scale * 2048 + 1024 +
                        (long long)a1 * first + (long long)a2 * second;
                    int sample = (int)(accumulator >> 11);
                    if (sample > 32767) sample = 32767;
                    if (sample < -32768) sample = -32768;
                    output[(size_t)written * 2 + channel] = (short)sample;
                    if (channels == 1) output[(size_t)written * 2 + 1] = (short)sample;
                    second = first; first = sample; ++written;
                }
            }
        }
        if (written != frames) return 0;
    }
    return 1;
}

static SND_AUX_REVERBHI room;
static int room_ready;
extern u32 orre_sample581_reads;
extern void* orre_sample581_address;
extern u32 orre_sample581_max_position;
extern u32 orre_sample581_outside_requests;
__declspec(dllexport) unsigned orre_sample581_count(void) { return orre_sample581_reads; }
__declspec(dllexport) unsigned orre_sample581_max(void) { return orre_sample581_max_position; }
__declspec(dllexport) unsigned orre_sample581_outside(void) { return orre_sample581_outside_requests; }

__declspec(dllexport) int orre_reverb(float coloration, float mix, float seconds,
                                      float damping, float pre_delay, float crosstalk) {
    room.coloration = coloration;
    room.mix = mix;
    room.time = seconds;
    room.damping = damping;
    room.preDelay = pre_delay;
    room.crosstalk = crosstalk;
    if (room_ready) return sndAuxCallbackUpdateSettingsReverbHI(&room);
    if (!sndAuxCallbackPrepareReverbHI(&room)) return 0;
    sndSetAuxProcessingCallbacks(0, sndAuxCallbackReverbHI, &room, 0xff, 0,
                                 NULL, NULL, 0xff, 0);
    room_ready = 1;
    return 1;
}

__declspec(dllexport) void orre_room_shutdown(void) {
    if (room_ready) {
        sndSetAuxProcessingCallbacks(0, NULL, NULL, 0xff, 0, NULL, NULL, 0xff, 0);
        sndAuxCallbackShutdownReverbHI(&room);
        room_ready = 0;
    }
}

__declspec(dllexport) int orre_init(unsigned rate) {
    static SND_HOOKS hooks = {malloc, free};
    SND_PC_CONFIG config = {rate, 2};
    sndSetHooks(&hooks);
    memset(&room, 0, sizeof(room));
    room_ready = 0;
    orre_sample581_reads = 0;
    orre_sample581_address = NULL;
    orre_sample581_max_position = 0;
    orre_sample581_outside_requests = 0;
    if (!sndPCConfigure(&config)) return -999;
    return sndInit(64, 48, 16, 1, 0, 0x9fc000);
}
