// Jarvis.app: a native window around the Jarvis page. It starts the local server (server.py) when needed,
// shows the page in WebKit, grants it the microphone, and stops the server on quit. The interface, the
// personality and the memory all live in the project folder, so changing them never needs a rebuild.
import AVFoundation
import Cocoa
import WebKit

let project = URL(fileURLWithPath: Bundle.main.object(forInfoDictionaryKey: "JarvisProject") as? String
                  ?? NSHomeDirectory() + "/Desktop/jarvis-voz")
let port = (try? JSONSerialization.jsonObject(with: Data(contentsOf: project.appendingPathComponent("config.json"))) as? [String: Any])?["port"] as? Int ?? 8765
let home = URL(string: "http://127.0.0.1:\(port)/")!
let background = NSColor(red: 0.012, green: 0.027, blue: 0.047, alpha: 1)

func jarvisConfig() -> [String: Any] {
    (try? JSONSerialization.jsonObject(with: Data(contentsOf: project.appendingPathComponent("config.json")))) as? [String: Any] ?? [:]
}

func appendLog(_ line: String) {
    let url = project.appendingPathComponent("jarvis.log")
    let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
    guard let data = "\(f.string(from: Date())) \(line)\n".data(using: .utf8), let h = try? FileHandle(forWritingTo: url) else { return }
    h.seekToEndOfFile(); h.write(data); try? h.close()
}

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKScriptMessageHandler, NSWindowDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    let claps = ClapDetector()
    var talking = false   // a conversation is open in the page (two claps then mute/unmute it)
    // F5 mutes Jarvis: the clap detector lets go of the microphone (the orange dot goes away) until F5 again.
    var muted = UserDefaults.standard.bool(forKey: "muted") {
        didSet { UserDefaults.standard.set(muted, forKey: "muted") }
    }
    lazy var muteKey = MuteKey { [weak self] in self?.toggleMute() }
    let hud = MuteHUD()
    var statusItem: NSStatusItem!

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        let config = WKWebViewConfiguration()
        config.mediaTypesRequiringUserActionForPlayback = []
        config.userContentController.addUserScript(WKUserScript(
            source: "document.documentElement.classList.add('in-app')", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        config.userContentController.add(self, name: "jarvis")
        web = WKWebView(frame: .zero, configuration: config)
        web.uiDelegate = self
        web.navigationDelegate = self
        web.setValue(false, forKey: "drawsBackground")

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 820),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Jarvis"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = background
        window.minSize = NSSize(width: 900, height: 600)
        window.contentView = web
        window.center()
        window.setFrameAutosaveName("JarvisWindow")
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        web.loadHTMLString(splash("Iniciando o Jarvis…"), baseURL: nil)
        AVCaptureDevice.requestAccess(for: .audio) { _ in }   // asks once, in Jarvis's own name
        startServer()

        claps.log = appendLog
        claps.strictness = Float(jarvisConfig()["clap_sensitivity"] as? Double ?? 1)
        claps.onDoubleClap = { [weak self] in self?.wake() }
        muteKey.install()
        buildStatusItem()
        if muted { appendLog("microfone: começa em silêncio (F5 liga)") }
        updateClaps()
    }

    // MARK: Mute (F5)

    @objc func toggleMute() {
        guard talking else { setMuted(!muted); return }
        // Mid-conversation the page's microphone decides (the button and claps change it too): only the mic stops, and is
        // released; the conversation and its tasks go on. 'off' = the page isn't live yet, so only the app's switch flips.
        web.evaluateJavaScript("window.jarvisClapMute ? window.jarvisClapMute() : 'off'") { [weak self] result, _ in
            guard let self else { return }
            let state = result as? String ?? "off"
            self.setMuted(state == "off" ? !self.muted : state == "muted")
        }
    }

    func setMuted(_ on: Bool) {
        muted = on
        appendLog(muted ? "microfone: silêncio (F5)" : "microfone: ouvindo de novo (F5)")
        NSSound(named: muted ? "Pop" : "Tink")?.play()
        hud.show(muted: muted)
        updateStatusItem()
        updateClaps()
    }

    func buildStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem.button?.target = self
        statusItem.button?.action = #selector(toggleMute)
        updateStatusItem()
    }

    func updateStatusItem() {
        let image = NSImage(systemSymbolName: muted ? "mic.slash" : "waveform", accessibilityDescription: muted ? "Jarvis em silêncio" : "Jarvis ouvindo")
        image?.isTemplate = true
        statusItem.button?.image = image
        statusItem.button?.toolTip = muted ? "Jarvis em silêncio. Clique ou aperte F5 para ligar." : "Jarvis ouvindo palmas. Clique ou aperte F5 para silenciar."
    }

    // Jarvis stays running when its window closes, so two claps (or the Dock icon) can bring it back.
    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { false }

    func applicationShouldHandleReopen(_ app: NSApplication, hasVisibleWindows: Bool) -> Bool {
        showWindow(); return true
    }

    // Closing works like any Mac app: the window closes (AppKit's own close, not orderOut) and Jarvis keeps
    // running in the Dock. A full-screen window first leaves full screen and closes once that ends; hiding it
    // while still in full screen left an empty, black full-screen Space with no way out but Quit.
    var closeAfterFullScreen = false

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        web.evaluateJavaScript("window.jarvisStop && window.jarvisStop()")   // closing ends the conversation and frees the mic
        talking = false
        updateClaps()
        if window.styleMask.contains(.fullScreen) {
            closeAfterFullScreen = true
            window.toggleFullScreen(nil)
            return false
        }
        return true
    }

    func windowDidExitFullScreen(_ note: Notification) {
        guard closeAfterFullScreen else { return }
        closeAfterFullScreen = false
        window.close()
    }

    func applicationWillTerminate(_ note: Notification) { claps.stop(); muteKey.uninstall(); server?.terminate() }

    func showWindow() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// Two claps: with no conversation they start one; during a conversation they mute or unmute it,
    /// through the page's own microphone button, so the button and the claps always agree.
    func wake() {
        guard talking else {
            NSSound(named: "Hero")?.play()
            showWindow()
            web.evaluateJavaScript("window.jarvisWake && window.jarvisWake()")
            return
        }
        web.evaluateJavaScript("window.jarvisClapMute ? window.jarvisClapMute() : 'off'") { result, _ in
            guard let state = result as? String, state != "off" else { return }
            NSSound(named: state == "muted" ? "Pop" : "Tink")?.play()
            appendLog(state == "muted" ? "palmas: microfone mudo" : "palmas: microfone de volta")
        }
    }

    func updateClaps() {
        guard jarvisConfig()["claps"] as? Bool ?? true, !muted else { claps.stop(); return }
        // Claps keep listening during a conversation too (to mute/unmute). When the page takes or releases its
        // echo-cancelled capture the audio setup changes, so start a fresh engine a moment later.
        claps.stop()
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { [weak self] in
            guard let self, !self.muted, jarvisConfig()["claps"] as? Bool ?? true else { return }
            self.claps.start()
        }
    }

    // MARK: Server

    func serverIsUp(_ done: @escaping (Bool) -> Void) {
        var req = URLRequest(url: home.appendingPathComponent("api/memory"), timeoutInterval: 1)
        req.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            done((resp as? HTTPURLResponse)?.statusCode == 200)
        }.resume()
    }

    func startServer() {
        serverIsUp { up in
            DispatchQueue.main.async {
                if !up { self.launchServer() }
                self.waitForServer(tries: 100)
            }
        }
    }

    func launchServer() {
        let p = Process()
        p.executableURL = project.appendingPathComponent(".venv/bin/python")
        p.arguments = ["server.py"]
        p.currentDirectoryURL = project
        // Start clean even when Jarvis itself was opened from a Claude Code or Atticus session.
        p.environment = ProcessInfo.processInfo.environment.filter { key, _ in
            !["CLAUDE", "ATTICUS_", "AI_AGENT", "ANTHROPIC_", "MCP_", "OTEL_"].contains { key.hasPrefix($0) }
        }
        let logURL = project.appendingPathComponent("jarvis.log")
        if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
        if let log = try? FileHandle(forWritingTo: logURL) {
            log.seekToEndOfFile()
            p.standardOutput = log
            p.standardError = log
        }
        do { try p.run(); server = p } catch {
            web.loadHTMLString(splash("Não consegui iniciar o servidor do Jarvis:<br>\(error.localizedDescription)"), baseURL: nil)
        }
    }

    func waitForServer(tries: Int) {
        serverIsUp { up in
            DispatchQueue.main.async {
                if up { self.web.load(URLRequest(url: home)); return }
                if tries <= 0 || self.server?.isRunning == false {
                    self.web.loadHTMLString(self.splash("O servidor do Jarvis não respondeu. Veja <code>jarvis.log</code> na pasta jarvis-voz."), baseURL: nil)
                    return
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { self.waitForServer(tries: tries - 1) }
            }
        }
    }

    func splash(_ text: String) -> String {
        """
        <html><body style="margin:0;height:100vh;display:grid;place-items:center;background:#03070c;color:#6f8aa3;
        font:600 14px -apple-system;letter-spacing:.2em;text-align:center">\(text)</body></html>
        """
    }

    // MARK: Page → app

    // The page calls window.webkit.messageHandlers.jarvis.postMessage({screen: true}) when the user turns Vision on.
    // Screenshots are taken by the server (a child of this app), so the Screen Recording permission must be Jarvis's.
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any] else { return }
        if let listening = body["listening"] as? Bool {   // conversation started or ended in the page
            talking = listening
            updateClaps()
        }
        if body["claps"] != nil { updateClaps() }   // the PALMAS switch changed config.json
        if let line = body["log"] as? String { appendLog("página: " + line) }
        if body["taskDone"] as? Bool == true {   // a task ended while the user wasn't listening: a short sound, and the Dock if away
            NSSound(named: "Glass")?.play()
            if !NSApp.isActive { NSApp.requestUserAttention(.informationalRequest) }
        }
        if body["screen"] as? Bool == true {
            let granted = CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess()
            web.evaluateJavaScript("window.screenAccess && window.screenAccess(\(granted))")
        }
    }

    // MARK: WebKit

    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo,
                 type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(origin.host == "127.0.0.1" ? .grant : .deny)
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo,
                 completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = false
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }

    // Links to anything but the Jarvis page (Obsidian, websites) open in their own apps.
    // Frames inside the page (the YouTube player of the study screen) load in place.
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let frame = action.targetFrame, !frame.isMainFrame {
            decisionHandler(.allow)
            return
        }
        if let url = action.request.url, url.host != "127.0.0.1", url.scheme != "about", url.scheme != "data" {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { NSWorkspace.shared.open(url) }
        return nil
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

    // MARK: Menu

    func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Sobre o Jarvis", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Abrir pasta do Jarvis", action: #selector(openFolder), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Ocultar Jarvis", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Encerrar Jarvis", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "Editar")
        edit.addItem(withTitle: "Desfazer", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "Refazer", action: Selector(("redo:")), keyEquivalent: "Z")
        edit.addItem(.separator())
        edit.addItem(withTitle: "Recortar", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Copiar", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Colar", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Selecionar tudo", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit

        let viewItem = NSMenuItem(); main.addItem(viewItem)
        let view = NSMenu(title: "Visualizar")
        view.addItem(withTitle: "Recarregar", action: #selector(reloadPage), keyEquivalent: "r")
        viewItem.submenu = view

        let windowItem = NSMenuItem(); main.addItem(windowItem)
        let win = NSMenu(title: "Janela")
        win.addItem(withTitle: "Minimizar", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        win.addItem(withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        let full = win.addItem(withTitle: "Entrar em Tela Cheia", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        full.keyEquivalentModifierMask = [.command, .control]
        win.addItem(withTitle: "Fechar Janela", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        windowItem.submenu = win
        NSApp.windowsMenu = win
        NSApp.mainMenu = main
    }

    @objc func reloadPage() { web.reload() }
    @objc func openFolder() { NSWorkspace.shared.open(project) }
}
