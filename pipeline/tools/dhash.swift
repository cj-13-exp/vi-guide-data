import Foundation
import CoreGraphics
import ImageIO
// usage: dhash <image> [cols cellW cellH]  -> "<index> <16 hex digits>" per image (or per cell of a sprite sheet)
// 64-bit difference hash on a 9x8 grayscale thumbnail: near-identical pictures differ in only a few bits.
let a = CommandLine.arguments
guard a.count >= 2, let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: a[1]) as CFURL, nil), let im = CGImageSourceCreateImageAtIndex(src, 0, nil) else { print("load fail"); exit(1) }
let cols = a.count >= 5 ? Int(a[2])! : 1, cw = a.count >= 5 ? Int(a[3])! : im.width, ch = a.count >= 5 ? Int(a[4])! : im.height
let rows = max(1, im.height / ch)
var idx = 0
for r in 0..<rows {
    for c in 0..<cols {
        guard c * cw + cw <= im.width, r * ch + ch <= im.height, let cell = im.cropping(to: CGRect(x: c * cw, y: r * ch, width: cw, height: ch)) else { continue }
        var px = [UInt8](repeating: 0, count: 9 * 8)
        let ctx = CGContext(data: &px, width: 9, height: 8, bitsPerComponent: 8, bytesPerRow: 9, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)!
        ctx.interpolationQuality = .medium
        ctx.draw(cell, in: CGRect(x: 0, y: 0, width: 9, height: 8))
        var h: UInt64 = 0
        for y in 0..<8 { for x in 0..<8 { h = (h << 1) | (px[y * 9 + x] > px[y * 9 + x + 1] ? 1 : 0) } }
        print(idx, String(format: "%016llx", h))
        idx += 1
    }
}
