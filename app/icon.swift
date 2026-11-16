// Draws the Jarvis app icon (an arc-reactor style ring) as a 1024×1024 PNG: swift icon.swift out.png
import AppKit

let size: CGFloat = 1024
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()
let ctx = NSGraphicsContext.current!.cgContext
let c = CGPoint(x: size / 2, y: size / 2)
let cyan = NSColor(red: 0.255, green: 0.827, blue: 1, alpha: 1)

// Rounded-square base, deep navy
let base = NSBezierPath(roundedRect: NSRect(x: 100, y: 100, width: 824, height: 824), xRadius: 185, yRadius: 185)
NSGradient(colors: [NSColor(red: 0.05, green: 0.10, blue: 0.16, alpha: 1), NSColor(red: 0.01, green: 0.03, blue: 0.05, alpha: 1)])!
    .draw(in: base, relativeCenterPosition: NSPoint(x: 0, y: 0.2))

ctx.setShadow(offset: .zero, blur: 28, color: cyan.withAlphaComponent(0.9).cgColor)
func ring(_ r: CGFloat, _ width: CGFloat, _ alpha: CGFloat, dash: [CGFloat] = []) {
    ctx.setStrokeColor(cyan.withAlphaComponent(alpha).cgColor)
    ctx.setLineWidth(width)
    ctx.setLineDash(phase: 0, lengths: dash)
    ctx.addArc(center: c, radius: r, startAngle: 0, endAngle: .pi * 2, clockwise: false)
    ctx.strokePath()
}
ring(330, 10, 0.85, dash: [210, 60, 40, 60])
ring(282, 4, 0.5)
for i in 0..<60 {   // tick marks
    let a = CGFloat(i) * .pi / 30, r1: CGFloat = 238, r2: CGFloat = i % 5 == 0 ? 262 : 252
    ctx.setLineDash(phase: 0, lengths: [])
    ctx.setStrokeColor(cyan.withAlphaComponent(0.6).cgColor); ctx.setLineWidth(i % 5 == 0 ? 6 : 3)
    ctx.move(to: CGPoint(x: c.x + r1 * cos(a), y: c.y + r1 * sin(a))); ctx.addLine(to: CGPoint(x: c.x + r2 * cos(a), y: c.y + r2 * sin(a)))
    ctx.strokePath()
}
ring(196, 22, 0.95, dash: [96, 18])
ring(160, 3, 0.6)

// Glowing core
let core = NSGradient(colors: [.white, cyan, cyan.withAlphaComponent(0)], atLocations: [0, 0.35, 1], colorSpace: .deviceRGB)!
core.draw(in: NSBezierPath(ovalIn: NSRect(x: c.x - 140, y: c.y - 140, width: 280, height: 280)), relativeCenterPosition: .zero)
image.unlockFocus()

let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
