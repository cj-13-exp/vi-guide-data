import Foundation
import CoreGraphics
import ImageIO
// usage: sharp <image> <cols> <cellW> <cellH>   -> one line per cell: "<index> <laplacian variance>" (lower = blurrier)
// For a single image pass cols=1 and the image size as cell size.
let a = CommandLine.arguments
guard a.count == 5, let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: a[1]) as CFURL, nil), let im = CGImageSourceCreateImageAtIndex(src, 0, nil) else { print("load fail"); exit(1) }
let cols = Int(a[2])!, cw = Int(a[3])!, ch = Int(a[4])!
let w = im.width, h = im.height
var gray = [UInt8](repeating: 0, count: w * h)
let ctx = CGContext(data: &gray, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)!
ctx.draw(im, in: CGRect(x: 0, y: 0, width: w, height: h))
let rows = max(1, h / ch)
var idx = 0
for r in 0..<rows {
    for c in 0..<cols {
        let x0 = c * cw, y0 = r * ch
        if x0 + cw > w || y0 + ch > h { continue }
        var sum = 0.0, sum2 = 0.0, n = 0.0
        for y in (y0 + 1)..<(y0 + ch - 1) {
            for x in (x0 + 1)..<(x0 + cw - 1) {
                let v = 4 * Int(gray[y * w + x]) - Int(gray[y * w + x - 1]) - Int(gray[y * w + x + 1]) - Int(gray[(y - 1) * w + x]) - Int(gray[(y + 1) * w + x])
                let d = Double(v); sum += d; sum2 += d * d; n += 1
            }
        }
        let mean = sum / n
        print(idx, String(format: "%.1f", sum2 / n - mean * mean))
        idx += 1
    }
}
