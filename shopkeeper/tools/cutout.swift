// Lift the product off its background using Vision's foreground-instance mask -
// the same engine as "Remove Background" in Preview. rembg was the obvious
// route and is unusable here: onnxruntime has no build for Python 3.14.
//
// Usage: swift cutout.swift in.png out.png
import Foundation
import Vision
import CoreImage
import AppKit

let args = CommandLine.arguments
guard args.count >= 3 else { print("need in and out"); exit(1) }
guard let src = CIImage(contentsOf: URL(fileURLWithPath: args[1])) else {
    print("cannot read \(args[1])"); exit(1)
}
let handler = VNImageRequestHandler(ciImage: src, options: [:])
let req = VNGenerateForegroundInstanceMaskRequest()
do { try handler.perform([req]) } catch { print("vision failed: \(error)"); exit(1) }
guard let obs = req.results?.first else { print("no subject found"); exit(1) }

// mask every instance it found, so a drawer sticking out is not dropped
let all = obs.allInstances
guard let masked = try? obs.generateMaskedImage(ofInstances: all,
                                                from: handler,
                                                croppedToInstancesExtent: true)
else { print("mask failed"); exit(1) }

let ci = CIImage(cvPixelBuffer: masked)
// composite onto pure white - an e-commerce plate, not transparency
let white = CIImage(color: .white).cropped(to: ci.extent)
let out = ci.composited(over: white)
let ctx = CIContext()
guard let cg = ctx.createCGImage(out, from: out.extent) else { print("render failed"); exit(1) }
let rep = NSBitmapImageRep(cgImage: cg)
guard let data = rep.representation(using: .png, properties: [:]) else { exit(1) }
try data.write(to: URL(fileURLWithPath: args[2]))
print("ok \(Int(out.extent.width))x\(Int(out.extent.height))")
