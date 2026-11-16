// jarvis-gravar: records the main display and the Mac's own sound (not the microphone) into an .mp4, so Jarvis can
// watch videos that can't be downloaded (private course platforms). Lives inside Jarvis.app so it uses Jarvis's
// Screen Recording permission. Usage: jarvis-gravar <out.mp4> [bundle id] [window title part]; stops on a "stop" line on stdin, EOF, or SIGTERM.
// Without a bundle id: the main display and all sound except Jarvis's. With one (com.google.Chrome): only that app's
// biggest window and only that app's sound, so the user can keep using the Mac while a lesson plays behind other windows.
import AppKit
import ScreenCaptureKit

final class Recorder: NSObject, SCRecordingOutputDelegate, SCStreamOutput {
    var stream: SCStream?
    let finished = DispatchSemaphore(value: 0)
    var failure: Error?

    func start(_ url: URL, app bundle: String?, title: String?) async throws {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: bundle == nil)
        let cfg = SCStreamConfiguration()
        let filter: SCContentFilter
        if let bundle {
            // Covered windows still count; minimized ones and other Spaces don't, so they can't be recorded.
            var windows = content.windows.filter { $0.owningApplication?.bundleIdentifier == bundle && $0.windowLayer == 0 && $0.frame.width > 300 && $0.frame.height > 200 }
            if let title, !title.isEmpty, windows.contains(where: { ($0.title ?? "").contains(title) }) {
                windows = windows.filter { ($0.title ?? "").contains(title) }   // the window showing the lesson's tab
            }
            guard let window = windows.max(by: { $0.frame.width * $0.frame.height < $1.frame.width * $1.frame.height }),
                  let app = window.owningApplication,
                  let display = content.displays.first(where: { $0.frame.intersects(window.frame) }) ?? content.displays.first else {
                throw NSError(domain: "gravar", code: 1, userInfo: [NSLocalizedDescriptionKey: "nenhuma janela aberta de \(bundle) (minimizada não serve)"])
            }
            // Every other app is left out: their windows on top vanish and their sound is muted. Chrome plays sound from
            // helper processes that aren't "apps", so including only Chrome (or only its window) records silence.
            let others = content.applications.filter { $0.processID != app.processID }
            filter = SCContentFilter(display: display, excludingApplications: others, exceptingWindows: [])
            let r = window.frame.offsetBy(dx: -display.frame.minX, dy: -display.frame.minY)
            cfg.sourceRect = r
            cfg.width = Int(r.width); cfg.height = Int(r.height)
            print("janela \(window.windowID) \(Int(r.width))x\(Int(r.height)) \(window.title ?? "")")
        } else {
            guard let display = content.displays.first(where: { $0.displayID == CGMainDisplayID() }) ?? content.displays.first else {
                throw NSError(domain: "gravar", code: 1, userInfo: [NSLocalizedDescriptionKey: "nenhuma tela encontrada"])
            }
            let jarvis = content.applications.filter { $0.bundleIdentifier == Bundle.main.bundleIdentifier }   // the app it lives in
            filter = SCContentFilter(display: display, excludingApplications: jarvis, exceptingWindows: [])
            cfg.width = display.width            // points, not pixels: readable text, a small file
            cfg.height = display.height
        }
        cfg.minimumFrameInterval = CMTime(value: 1, timescale: 10)   // Gemini looks at 1 frame a second; 10 is plenty
        cfg.capturesAudio = true
        cfg.sampleRate = 48000
        cfg.channelCount = 2
        cfg.excludesCurrentProcessAudio = true
        let stream = SCStream(filter: filter, configuration: cfg, delegate: nil)
        // shortcut: no-op outputs so the stream delivers audio to the recording on every macOS 15+ build.
        try stream.addStreamOutput(self, type: .screen, sampleHandlerQueue: .global())
        try stream.addStreamOutput(self, type: .audio, sampleHandlerQueue: .global())
        let rc = SCRecordingOutputConfiguration()
        rc.outputURL = url
        rc.outputFileType = .mp4
        rc.videoCodecType = .h264
        try stream.addRecordingOutput(SCRecordingOutput(configuration: rc, delegate: self))
        try await stream.startCapture()
        self.stream = stream
    }

    func stop() async {
        do { try await stream?.stopCapture() } catch { failure = error; finished.signal() }
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {}
    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) { print("gravando"); fflush(stdout) }
    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) { failure = error; finished.signal() }
    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) { finished.signal() }
}

@main
struct Gravar {
    static func main() async {
        let args = CommandLine.arguments
        guard (2...4).contains(args.count) else { fputs("uso: jarvis-gravar <saida.mp4> [bundle id] [parte do título da janela]\n", stderr); exit(2) }
        _ = NSApplication.shared   // window capture needs a window-server connection (CGS init), even without UI
        let url = URL(fileURLWithPath: CommandLine.arguments[1])
        try? FileManager.default.removeItem(at: url)
        let rec = Recorder()
        do { try await rec.start(url, app: args.count >= 3 ? args[2] : nil, title: args.count == 4 ? args[3] : nil) } catch { fputs("falhou ao começar: \(error.localizedDescription)\n", stderr); exit(1) }

        let stopNow = DispatchSemaphore(value: 0)
        signal(SIGTERM, SIG_IGN); signal(SIGINT, SIG_IGN)
        let signals = [SIGTERM, SIGINT].map { DispatchSource.makeSignalSource(signal: $0, queue: .global()) }
        signals.forEach { $0.setEventHandler { stopNow.signal() }; $0.resume() }
        Thread.detachNewThread {
            while let line = readLine(), line.trimmingCharacters(in: .whitespaces) != "stop" {}
            stopNow.signal()   // "stop" or EOF (the server went away): finish the file instead of losing it
        }
        await withCheckedContinuation { c in DispatchQueue.global().async { stopNow.wait(); c.resume() } }
        await rec.stop()
        await withCheckedContinuation { c in DispatchQueue.global().async { _ = rec.finished.wait(timeout: .now() + 30); c.resume() } }
        if let e = rec.failure { fputs("falhou: \(e.localizedDescription)\n", stderr); exit(1) }
        print("pronto"); exit(0)
    }
}
