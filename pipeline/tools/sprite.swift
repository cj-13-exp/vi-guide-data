import AppKit
// usage: sprite <out.jpg> <cols> <cellW> <cellH> <img>...  (cover-crops each image into its cell)
let a = CommandLine.arguments
let cols = Int(a[2])!, cw = Int(a[3])!, ch = Int(a[4])!
let files = Array(a[5...]); let rows = (files.count + cols - 1) / cols
let ctx = CGContext(data: nil, width: cols*cw, height: rows*ch, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctx.setFillColor(CGColor(red: 0.08, green: 0.09, blue: 0.17, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: cols*cw, height: rows*ch))
ctx.interpolationQuality = .high
for (i, f) in files.enumerated() {
  guard let im = NSImage(contentsOfFile: f), let cg = im.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("skip", f); continue }
  let s = max(CGFloat(cw)/CGFloat(cg.width), CGFloat(ch)/CGFloat(cg.height))
  let w = CGFloat(cg.width)*s, h = CGFloat(cg.height)*s
  let x = CGFloat((i % cols)*cw), y = CGFloat((rows - 1 - i/cols)*ch)
  ctx.saveGState(); ctx.clip(to: CGRect(x: x, y: y, width: CGFloat(cw), height: CGFloat(ch)))
  ctx.draw(cg, in: CGRect(x: x + (CGFloat(cw)-w)/2, y: y + (CGFloat(ch)-h)/2, width: w, height: h)); ctx.restoreGState()
}
let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
try! rep.representation(using: .jpeg, properties: [.compressionFactor: 0.8])!.write(to: URL(fileURLWithPath: a[1]))
print("sheet", cols, rows)
