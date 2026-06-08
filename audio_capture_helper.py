import argparse
import os
import sys
import time

import numpy as np
import soundcard as sc


def _debug(message):
    if os.environ.get("TODD_AUDIO_HELPER_DEBUG"):
        print(message, file=sys.stderr, flush=True)


def _mono_int16(block):
    if block is None or len(block) == 0:
        return b""
    arr = np.asarray(block, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    arr = np.clip(arr, -1.0, 1.0)
    return (arr * 32767.0).astype("<i2", copy=False).tobytes()


def _pcm_bytes_to_mono_int16(data, channels, input_rate, output_rate, output_frames):
    if not data:
        return b""
    samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
    if channels > 1:
        samples = samples[: len(samples) - (len(samples) % channels)]
        samples = samples.reshape(-1, channels).mean(axis=1)
    if input_rate != output_rate or len(samples) != output_frames:
        if len(samples) == 0:
            samples = np.zeros(output_frames, dtype=np.float32)
        else:
            old_x = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
            new_x = np.linspace(0.0, 1.0, num=output_frames, endpoint=False)
            samples = np.interp(new_x, old_x, samples).astype(np.float32)
    samples = np.clip(samples, -32768, 32767)
    return samples.astype("<i2", copy=False).tobytes()


def _capture_system_wasapi(sample_rate, chunk):
    _debug("wasapi: import")
    import pyaudiowpatch as pyaudio

    _debug("wasapi: init")
    audio = pyaudio.PyAudio()
    stream = None
    try:
        device = audio.get_default_wasapi_loopback()
        _debug(f"wasapi: device={device.get('name')} rate={device.get('defaultSampleRate')}")
        native_rate = int(device.get("defaultSampleRate") or sample_rate)
        channels = min(2, max(1, int(device.get("maxInputChannels") or 1)))
        native_chunk = max(1, int(round(chunk * native_rate / float(sample_rate))))
        _debug(f"wasapi: open native_rate={native_rate} channels={channels} native_chunk={native_chunk}")
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=native_rate,
            input=True,
            input_device_index=int(device["index"]),
            frames_per_buffer=native_chunk,
        )
        _debug("wasapi: recording")
        while True:
            data = stream.read(native_chunk, exception_on_overflow=False)
            sys.stdout.buffer.write(_pcm_bytes_to_mono_int16(data, channels, native_rate, sample_rate, chunk))
            sys.stdout.buffer.flush()
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        audio.terminate()


def _capture_mixed_wasapi(sample_rate, chunk):
    _debug("wasapi-mixed: import")
    import pyaudiowpatch as pyaudio

    _debug("wasapi-mixed: init")
    audio = pyaudio.PyAudio()
    mic_stream = None
    sys_stream = None
    try:
        loopback = audio.get_default_wasapi_loopback()
        _debug(f"wasapi-mixed: device={loopback.get('name')} rate={loopback.get('defaultSampleRate')}")
        loopback_rate = int(loopback.get("defaultSampleRate") or sample_rate)
        loopback_channels = min(2, max(1, int(loopback.get("maxInputChannels") or 1)))
        loopback_chunk = max(1, int(round(chunk * loopback_rate / float(sample_rate))))
        mic_stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk,
        )
        sys_stream = audio.open(
            format=pyaudio.paInt16,
            channels=loopback_channels,
            rate=loopback_rate,
            input=True,
            input_device_index=int(loopback["index"]),
            frames_per_buffer=loopback_chunk,
        )
        while True:
            mic = np.frombuffer(mic_stream.read(chunk, exception_on_overflow=False), dtype="<i2").astype(np.float32)
            system = np.frombuffer(
                _pcm_bytes_to_mono_int16(
                    sys_stream.read(loopback_chunk, exception_on_overflow=False),
                    loopback_channels,
                    loopback_rate,
                    sample_rate,
                    chunk,
                ),
                dtype="<i2",
            ).astype(np.float32)
            mixed = np.clip((mic[:chunk] + system[:chunk]) * 0.5, -32768, 32767)
            sys.stdout.buffer.write(mixed.astype("<i2", copy=False).tobytes())
            sys.stdout.buffer.flush()
    finally:
        for stream in (mic_stream, sys_stream):
            if stream:
                stream.stop_stream()
                stream.close()
        audio.terminate()


def _find_loopback():
    speaker = sc.default_speaker()
    return sc.get_microphone(speaker.id, include_loopback=True)


def _capture_single(source, sample_rate, chunk):
    device = sc.default_microphone() if source == "microphone" else _find_loopback()
    with device.recorder(samplerate=sample_rate, channels=2, blocksize=chunk) as recorder:
        while True:
            data = recorder.record(numframes=chunk)
            sys.stdout.buffer.write(_mono_int16(data))
            sys.stdout.buffer.flush()


def _capture_mixed(sample_rate, chunk):
    mic = sc.default_microphone()
    loopback = _find_loopback()
    with mic.recorder(samplerate=sample_rate, channels=2, blocksize=chunk) as mic_rec, loopback.recorder(
        samplerate=sample_rate, channels=2, blocksize=chunk
    ) as sys_rec:
        while True:
            mic_data = np.asarray(mic_rec.record(numframes=chunk), dtype=np.float32)
            sys_data = np.asarray(sys_rec.record(numframes=chunk), dtype=np.float32)
            if mic_data.ndim == 2:
                mic_data = mic_data.mean(axis=1)
            if sys_data.ndim == 2:
                sys_data = sys_data.mean(axis=1)
            n = min(len(mic_data), len(sys_data))
            if n <= 0:
                time.sleep(chunk / float(sample_rate))
                continue
            mixed = np.clip((mic_data[:n] + sys_data[:n]) * 0.5, -1.0, 1.0)
            sys.stdout.buffer.write((mixed * 32767.0).astype("<i2", copy=False).tobytes())
            sys.stdout.buffer.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("system", "both"), required=True)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--chunk", type=int, default=1024)
    args = parser.parse_args()

    try:
        if args.mode == "both":
            _capture_mixed_wasapi(args.sample_rate, args.chunk)
        else:
            _capture_system_wasapi(args.sample_rate, args.chunk)
    except Exception as exc:
        _debug(f"wasapi failed: {exc!r}; falling back to soundcard")
        if args.mode == "both":
            _capture_mixed(args.sample_rate, args.chunk)
        else:
            _capture_single("system", args.sample_rate, args.chunk)


if __name__ == "__main__":
    main()
