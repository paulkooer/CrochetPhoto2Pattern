// Render PDF pages to PNG and extract their text with the system PDFKit (no installs).
// Usage: swift pdf_pages.swift <file.pdf> <out-dir> [comma-separated 1-based pages]
import AppKit
import Foundation
import PDFKit

let arguments = CommandLine.arguments
guard arguments.count >= 3, let document = PDFDocument(url: URL(fileURLWithPath: arguments[1])) else {
    FileHandle.standardError.write("cannot open PDF\n".data(using: .utf8)!)
    exit(2)
}
let outDir = arguments[2]
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)
print("pages: \(document.pageCount)")
let wanted: [Int] = arguments.count > 3
    ? arguments[3].split(separator: ",").compactMap { Int($0) }
    : Array(1...document.pageCount)
var allText = ""
for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { continue }
    let text = page.string ?? ""
    allText += "\n===== page \(index + 1) =====\n" + text
    guard wanted.contains(index + 1) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let scale: CGFloat = 1.6
    let width = Int(bounds.width * scale), height = Int(bounds.height * scale)
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
                                        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
          let context = NSGraphicsContext(bitmapImageRep: bitmap) else { continue }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    context.cgContext.setFillColor(NSColor.white.cgColor)
    context.cgContext.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.cgContext.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: context.cgContext)
    NSGraphicsContext.restoreGraphicsState()
    if let png = bitmap.representation(using: .png, properties: [:]) {
        try? png.write(to: URL(fileURLWithPath: "\(outDir)/page-\(index + 1).png"))
    }
}
try? allText.write(toFile: "\(outDir)/text.txt", atomically: true, encoding: .utf8)
print("characters extracted: \(allText.count)")
