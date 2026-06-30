"""Generate high-quality, seamless site ground textures for the 3D viewer.

Outputs 512x512 tileable PNGs (grass / asphalt / concrete) used by the xeokit
structure-mode site context (web/public/textures/site/*.png). Seamlessness comes
from building the fractal noise in the frequency domain (an inverse FFT of a 1/f
spectrum is inherently periodic, so the tile wraps with no visible seam).

Run: python scripts/gen_site_textures.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 512
OUT = Path(__file__).resolve().parents[1] / "web" / "public" / "textures" / "site"


def fbm(size: int, beta: float, seed: int) -> np.ndarray:
    """Seamless fractal (1/f^beta) noise in [0, 1]."""
    rng = np.random.default_rng(seed)
    fx = np.fft.fftfreq(size)[:, None]
    fy = np.fft.fftfreq(size)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    spectrum = (rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size)))
    spectrum /= f ** (beta / 2.0)
    img = np.fft.ifft2(spectrum).real
    img -= img.min()
    img /= max(img.max(), 1e-9)
    return img


def speckle(size: int, density: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.random((size, size)) < density).astype(np.float32)


def lerp(a, b, t):
    return a + (b - a) * t[..., None]


def save(name: str, rgb: np.ndarray) -> None:
    arr = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB").convert("RGBA")
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{name}.png")
    print(f"  wrote {name}.png  {img.size}")


def make_grass() -> None:
    base = fbm(SIZE, beta=2.4, seed=11)          # large mottling
    fine = fbm(SIZE, beta=1.2, seed=12)          # blade-scale detail
    patch = fbm(SIZE, beta=3.4, seed=13)         # broad lighter/darker patches
    dark = np.array([0.13, 0.30, 0.13])
    mid = np.array([0.22, 0.45, 0.20])
    light = np.array([0.38, 0.62, 0.30])
    t = np.clip(base * 0.6 + fine * 0.4, 0, 1)
    rgb = lerp(dark, mid, t)
    rgb = lerp(rgb, light, np.clip((patch - 0.45) * 1.6, 0, 1) * 0.6)
    # faint blade streaks
    rgb *= (0.9 + 0.1 * fine)[..., None]
    save("grass", rgb)


def make_asphalt() -> None:
    base = fbm(SIZE, beta=2.0, seed=21)
    grain = fbm(SIZE, beta=0.6, seed=22)         # fine aggregate
    stains = fbm(SIZE, beta=3.6, seed=23)        # broad lighter wear
    agg = speckle(SIZE, 0.04, seed=24)           # light aggregate flecks
    dark = np.array([0.10, 0.105, 0.12])
    mid = np.array([0.17, 0.18, 0.20])
    t = np.clip(base * 0.5 + grain * 0.5, 0, 1)
    rgb = lerp(dark, mid, t)
    rgb = lerp(rgb, mid * 1.35, np.clip((stains - 0.5) * 1.5, 0, 1) * 0.5)
    rgb += (agg * 0.18)[..., None]               # bright specks
    save("asphalt", rgb)


def make_concrete() -> None:
    base = fbm(SIZE, beta=2.6, seed=31)
    grain = fbm(SIZE, beta=0.8, seed=32)
    stains = fbm(SIZE, beta=3.8, seed=33)        # patchy discolouration
    pores = speckle(SIZE, 0.02, seed=34)         # tiny dark pits
    light = np.array([0.74, 0.74, 0.71])
    mid = np.array([0.60, 0.61, 0.59])
    t = np.clip(base * 0.55 + grain * 0.45, 0, 1)
    rgb = lerp(light, mid, t)
    rgb = lerp(rgb, mid * 0.88, np.clip((stains - 0.55) * 1.6, 0, 1) * 0.5)
    rgb -= (pores * 0.16)[..., None]
    save("concrete", rgb)


def main() -> None:
    print(f"Generating seamless {SIZE}x{SIZE} site textures -> {OUT}")
    make_grass()
    make_asphalt()
    make_concrete()
    print("done.")


if __name__ == "__main__":
    main()
