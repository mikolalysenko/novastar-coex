"""Render the project's original LED-grid icon (requires Pillow)."""

from pathlib import Path

from PIL import Image, ImageDraw

DEST = Path(__file__).resolve().parents[1] / "custom_components/novastar_coex/brand"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (1024, 1024))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 1023, 1023), radius=160, fill="#14263D")
    # An N made of illuminated pixels, with subdued pixels filling the LED wall.
    for row in range(5):
        for col in range(5):
            x, y = 128 + col * 160, 128 + row * 160
            lit = col in (0, 4) or row == col
            draw.rounded_rectangle(
                (x, y, x + 127, y + 127),
                radius=28,
                fill=("#5AE0C1" if row < 3 else "#5CB8FF") if lit else "#2B425A",
            )
    for size, name in [(256, "icon.png"), (512, "icon@2x.png")]:
        image.resize((size, size), Image.Resampling.LANCZOS).save(DEST / name, optimize=True)


if __name__ == "__main__":
    main()
