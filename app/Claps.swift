// Listens to the microphone for two claps in a row. Runs only on this Mac and keeps no audio: each ~10 ms block
// is reduced to a loudness number and thrown away. A clap is a sudden, loud spike that dies out within ~0.1 s
// (speech and music stay loud for longer); two of them 0.1–1.1 s apart call `onDoubleClap`.
import AVFoundation
import QuartzCore

final class ClapDetector {
    var onDoubleClap: () -> Void = {}
    var log: (String) -> Void = { _ in }
    /// Higher = needs a louder clap. 1 is the default; config.json "clap_sensitivity" can raise or lower it.
    var strictness: Float = 1

    // A fresh engine on every start: after the conversation's echo-cancelled capture, a reused engine comes back deaf.
    private var engine = AVAudioEngine()
    private var configObserver: NSObjectProtocol?
    private var blocks = 0, loudest: Float = 0, lastReport = 0.0
    private(set) var running = false
    private var noise: Float = 0.005          // running estimate of the room's background level (RMS)
    private var previous: Float = 0           // RMS of the block before
    private var onset: (time: Double, rms: Float, peak: Float)?
    private var tail: [Float] = []            // RMS of the blocks right after an onset
    private var lastClap = 0.0
    private var lastPeak: Float = 0
    private var quietUntil = 0.0

    func start() {
        guard !running else { return }
        engine = AVAudioEngine()
        lastClap = 0; onset = nil; tail = []; blocks = 0; loudest = 0
        // The mic changed (another app grabbed it, a headset was plugged in): start over on the new setup.
        configObserver = NotificationCenter.default.addObserver(forName: .AVAudioEngineConfigurationChange, object: engine, queue: .main) { [weak self] _ in
            guard let self, self.running else { return }
            self.log("palmas: microfone mudou, reiniciando")
            self.stop(); self.start()
        }
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0 else { log("palmas: sem microfone"); return }
        let block = AVAudioFrameCount(format.sampleRate / 100)   // ~10 ms
        input.installTap(onBus: 0, bufferSize: block, format: format) { [weak self] buffer, _ in self?.process(buffer) }
        do {
            try engine.start()
            running = true
            log("palmas: escutando")
        } catch {
            input.removeTap(onBus: 0)
            log("palmas: não consegui abrir o microfone (\(error.localizedDescription))")
        }
    }

    func stop() {
        if let o = configObserver { NotificationCenter.default.removeObserver(o); configObserver = nil }
        guard running else { return }
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        running = false
        onset = nil
        log("palmas: pausado")
    }

    private func process(_ buffer: AVAudioPCMBuffer) {
        guard let samples = buffer.floatChannelData?[0] else { return }
        let n = Int(buffer.frameLength)
        guard n > 0 else { return }
        var peak: Float = 0, sum: Float = 0
        for i in 0..<n { let v = abs(samples[i]); peak = max(peak, v); sum += v * v }
        let rms = (sum / Float(n)).squareRoot()
        let now = CACurrentMediaTime()
        defer { previous = rms }
        blocks += 1; loudest = max(loudest, peak)
        if now - lastReport > 300 {   // every 5 min: proof of life and levels, for tuning
            if lastReport > 0 { log(String(format: "palmas: ativo, ruído %.3f, pico máx %.2f", noise, loudest)) }
            lastReport = now; loudest = 0
        }

        if let o = onset {   // a candidate clap: it must fade fast to count
            tail.append(rms)
            if now - o.time < 0.12 { return }
            let after = tail.dropFirst(3)   // skip the first ~30 ms, the clap itself
            let mean = after.isEmpty ? 0 : after.reduce(0, +) / Float(after.count)
            onset = nil; tail = []
            guard mean < o.rms * 0.5 else { return }   // still loud: a voice, a song, a bang that rings on (0.5: room echo of a real clap is allowed)
            clap(at: o.time, peak: o.peak)
            return
        }
        noise = noise * 0.995 + min(rms, noise * 4) * 0.005
        let threshold = max(0.09, noise * 12) * strictness   // a normal clap measured 0.11–0.43 here; keyboard and voice stay near 0.03
        // A clap is a sharp crack: its peak towers over the block's average (crest), unlike a voice or a hum.
        if now > quietUntil, peak > threshold, peak > rms * 3, rms > previous * 3, rms > noise * 6 {
            onset = (now, rms, peak)
            tail = []
        }
    }

    private func clap(at time: Double, peak: Float) {
        let gap = time - lastClap
        let alike = lastPeak > 0 && peak / lastPeak > 0.33 && peak / lastPeak < 3   // two claps of similar strength
        if gap > 0.1 && gap < 1.0 && alike {
            lastClap = 0; lastPeak = 0
            quietUntil = time + 2.5   // one double clap, one wake
            log(String(format: "palmas: duas palmas (intervalo %.2fs, pico %.2f)", gap, peak))
            DispatchQueue.main.async { self.onDoubleClap() }
        } else {
            lastClap = time; lastPeak = peak
            log(String(format: "palmas: uma palma (pico %.2f, ruído %.3f)", peak, noise))
        }
    }
}
