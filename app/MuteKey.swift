// The F5 key (the one with the microphone icon) becomes Jarvis's mute switch, like the side switch on an iPhone.
// macOS sends that key as "Dictation"; while Jarvis runs, hidutil turns it into F18, a key nothing else uses,
// and a Carbon hot key catches F18 without needing the Accessibility permission. On quit the key goes back to
// Dictation. fn+F5 still sends a plain F5.
import Carbon
import Cocoa

final class MuteKey {
    private var hotKey: EventHotKeyRef?
    private var handler: EventHandlerRef?
    private let onPress: () -> Void
    private static let dictation: UInt64 = 0xC000000CF   // consumer page 0x0C, usage 0xCF
    private static let f18: UInt64 = 0x70000006D         // keyboard page 0x07, usage 0x6D

    init(onPress: @escaping () -> Void) { self.onPress = onPress }

    func install() {
        Self.remap("[{\"HIDKeyboardModifierMappingSrc\":\(Self.dictation),\"HIDKeyboardModifierMappingDst\":\(Self.f18)}]")
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        let me = Unmanaged.passUnretained(self).toOpaque()
        InstallEventHandler(GetApplicationEventTarget(), { _, _, data in
            guard let data else { return noErr }
            let key = Unmanaged<MuteKey>.fromOpaque(data).takeUnretainedValue()
            DispatchQueue.main.async { key.onPress() }
            return noErr
        }, 1, &spec, me, &handler)
        RegisterEventHotKey(UInt32(kVK_F18), 0, EventHotKeyID(signature: OSType(0x4A525653), id: 1),   // 'JRVS'
                            GetApplicationEventTarget(), 0, &hotKey)
    }

    func uninstall() {
        if let hotKey { UnregisterEventHotKey(hotKey) }
        if let handler { RemoveEventHandler(handler) }
        hotKey = nil; handler = nil
        Self.remap("[]")   // F5 is Dictation again
    }

    private static func remap(_ mapping: String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/hidutil")
        p.arguments = ["property", "--set", "{\"UserKeyMapping\":\(mapping)}"]
        p.standardOutput = FileHandle.nullDevice
        try? p.run(); p.waitUntilExit()
    }
}

/// A short on-screen notice, like the one the iPhone shows when the mute switch flips.
final class MuteHUD {
    private var panel: NSPanel?
    private var hide: DispatchWorkItem?

    func show(muted: Bool) {
        hide?.cancel()
        panel?.orderOut(nil)
        let size = NSSize(width: 230, height: 64)
        let p = NSPanel(contentRect: NSRect(origin: .zero, size: size), styleMask: [.borderless, .nonactivatingPanel],
                        backing: .buffered, defer: false)
        p.level = .statusBar
        p.isOpaque = false
        p.backgroundColor = .clear
        p.ignoresMouseEvents = true
        p.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

        let box = NSVisualEffectView(frame: NSRect(origin: .zero, size: size))
        box.material = .hudWindow
        box.state = .active
        box.wantsLayer = true
        box.layer?.cornerRadius = 32
        box.appearance = NSAppearance(named: .darkAqua)

        let icon = NSImageView(frame: NSRect(x: 20, y: 18, width: 28, height: 28))
        icon.image = NSImage(systemSymbolName: muted ? "mic.slash.fill" : "mic.fill", accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: 20, weight: .semibold))
        icon.contentTintColor = muted ? .systemRed : .white
        let label = NSTextField(labelWithString: muted ? "Jarvis em silêncio" : "Jarvis ouvindo")
        label.font = .systemFont(ofSize: 15, weight: .semibold)
        label.textColor = .white
        label.frame = NSRect(x: 58, y: 21, width: size.width - 70, height: 22)
        box.addSubview(icon); box.addSubview(label)
        p.contentView = box

        if let screen = NSScreen.main?.visibleFrame {
            p.setFrameOrigin(NSPoint(x: screen.midX - size.width / 2, y: screen.maxY - size.height - 24))
        }
        p.alphaValue = 0
        p.orderFrontRegardless()
        NSAnimationContext.runAnimationGroup { $0.duration = 0.15; p.animator().alphaValue = 1 }
        panel = p

        let work = DispatchWorkItem { [weak self, weak p] in
            guard let p else { return }
            NSAnimationContext.runAnimationGroup({ $0.duration = 0.3; p.animator().alphaValue = 0 }) {
                p.orderOut(nil)
                if self?.panel === p { self?.panel = nil }
            }
        }
        hide = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.4, execute: work)
    }
}
