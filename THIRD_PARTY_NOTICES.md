# Third-Party Code Notices

EmotiScreen contains narrowly adapted signal-processing and animation snippets. It does not include complete upstream repositories or their unrelated packages.

## pyAudioAnalysis

- Source: `pyAudioAnalysis/ShortTermFeatures.py`, Theodoros Giannakopoulos, Apache License 2.0.
- Upstream: https://github.com/tyiannak/pyAudioAnalysis/blob/master/pyAudioAnalysis/ShortTermFeatures.py
- Adapted in `emotionscreen/core/acoustic.py`: short-frame energy, zero-crossing, spectral centroid/flux, and autocorrelation feature logic. EmotiScreen retains only the small subset needed for short local windows and does not include the classifier, training flow, MFCC bank, or package dependencies.
- License copy: [`licenses/Apache-2.0-pyAudioAnalysis.txt`](licenses/Apache-2.0-pyAudioAnalysis.txt).

## TkAnimator

- Source: `tk_animations.py`, itsDevlune, MIT License, Copyright (c) 2025 itsDevLune.
- Upstream: https://github.com/itsDevlune/TkAnimator/blob/main/tk_animations.py
- Adapted in `emotionscreen/ui/comfort_window.py`: stepped alpha interpolation and a low-amplitude sinusoidal pulse. Scheduling uses cancellable Tk `after` callbacks and respects reduced-motion mode.
- License copy: [`licenses/MIT-TkAnimator.txt`](licenses/MIT-TkAnimator.txt).

## CTkMessagebox

- Source: `CTkMessagebox/ctkmessagebox.py`, Akash Bora, CC0-1.0.
- Upstream: https://github.com/Akascape/CTkMessagebox/blob/main/CTkMessagebox/ctkmessagebox.py
- Adapted in `emotionscreen/ui/comfort_window.py`: pointer-down drag anchor plus root-coordinate movement. The card remains a native Tk Canvas window; CustomTkinter and Pillow are not included.

## window-vibrancy

- Source: `src/windows.rs` from window-vibrancy 0.7.1, dual Apache-2.0/MIT.
- Upstream: https://docs.rs/crate/window-vibrancy/0.7.1/source/src/windows.rs
- Adapted in `emotionscreen/ui/glass.py`: Windows composition struct layout, acrylic state/flags, and supported-build fallback translated to Python ctypes. The crate itself is Rust/Tauri and is not copied or bundled.
- Selected MIT license copy: [`licenses/MIT-window-vibrancy.txt`](licenses/MIT-window-vibrancy.txt).

## llama.cpp

- Upstream: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- The existing local Clef adapter follows its System One contract; live audio does not enter that adapter.
