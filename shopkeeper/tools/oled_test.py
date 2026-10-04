# Minimal SH1106 test, run on the board.
#
# A 1.3" I2C OLED is an SH1106, not the SSD1306 of the 0.96". The two differ in
# one way that matters: the SH1106's RAM is 132 columns wide against a 128-pixel
# panel, so the visible window starts at column 2. Drive it with an SSD1306
# driver and everything sits 2 px left with the wrap showing down the edge.
#
# This draws a border hard against all four edges. If the border is even and
# touches every side, the offset is right and the part is an SH1106.
from machine import Pin, I2C
import framebuf, time

SCL, SDA, ADDR = 2, 1, 0x3C
W, H = 128, 64
COL_OFFSET = 2                      # the whole point

i2c = I2C(0, scl=Pin(SCL), sda=Pin(SDA), freq=400000)


def cmd(c):
    i2c.writeto(ADDR, bytes([0x80, c]))


# 0xAD 0x8B - "internal DC-DC on" - is deliberately NOT here. Sending it wedged
# this module: it ACKed every transaction up to that point and then went silent
# until the rail was cycled. Modules that carry their own boost regulator do not
# want the controller driving one too. If the panel stays dark, add it back.
INIT = (0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40,
        0xA1, 0xC8, 0xDA, 0x12, 0x81, 0x7F,
        0xD9, 0x22, 0xDB, 0x35, 0xA4, 0xA6, 0xAF)
for c in INIT:
    cmd(c)

buf = bytearray(W * H // 8)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.MONO_VLSB)


def show():
    for page in range(H // 8):
        cmd(0xB0 | page)
        cmd(0x00 | (COL_OFFSET & 0x0F))
        cmd(0x10 | (COL_OFFSET >> 4))
        i2c.writeto(ADDR, b"\x40" + buf[page*W:(page+1)*W])


# 1. every pixel on - proves power, bus and panel
fb.fill(1); show(); time.sleep(1.0)
fb.fill(0); show(); time.sleep(0.3)

# 2. border flush to all four edges + text
fb.fill(0)
fb.rect(0, 0, W, H, 1)
fb.rect(2, 2, W-4, H-4, 1)
fb.text("shopkeeper", 24, 12, 1)
fb.text("NANO", 46, 24, 1)
fb.text("SH1106 128x64", 12, 42, 1)
fb.text("SCL2 SDA1 0x3C", 8, 52, 1)
show()

print("OK addr=0x%02X  %dx%d  col_offset=%d" % (ADDR, W, H, COL_OFFSET))
print("look at it: border should touch all four edges")
