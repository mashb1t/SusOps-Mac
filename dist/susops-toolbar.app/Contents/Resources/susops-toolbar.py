import os
import subprocess
import rumps
import objc
from Cocoa import (
    NSPanel, NSTextField, NSView, NSMakeRect, NSButton, NSAlert, NSApplication
)
from AppKit import (
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel
)

class PrefsPanel(NSPanel):
    """A floating panel with SSH Host, SOCKS Port & PAC Port fields plus Save/Cancel."""
    def initWithContentRect_styleMask_backing_defer_(
        self, frame, style, backing, defer
    ):
        self = objc.super(PrefsPanel, self).initWithContentRect_styleMask_backing_defer_(
            frame, style, backing, defer
        )
        if not self:
            return None

        self.setTitle_("SusOps Preferences")
        self.setLevel_(NSFloatingWindowLevel)

        content = self.contentView()

        # --- SSH Host ---
        lbl1 = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 156, 100, 24))
        lbl1.setStringValue_("SSH Host:")
        lbl1.setBezeled_(False)
        lbl1.setDrawsBackground_(False)
        lbl1.setEditable_(False)
        content.addSubview_(lbl1)

        self.ssh_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 156, 160, 24))
        content.addSubview_(self.ssh_field)

        # --- SOCKS Port ---
        lbl2 = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 116, 100, 24))
        lbl2.setStringValue_("SOCKS Port:")
        lbl2.setBezeled_(False)
        lbl2.setDrawsBackground_(False)
        lbl2.setEditable_(False)
        content.addSubview_(lbl2)

        self.socks_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 116, 160, 24))
        content.addSubview_(self.socks_field)

        # --- PAC Port ---
        lbl3 = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 76, 100, 24))
        lbl3.setStringValue_("PAC Port:")
        lbl3.setBezeled_(False)
        lbl3.setDrawsBackground_(False)
        lbl3.setEditable_(False)
        content.addSubview_(lbl3)

        self.pac_field = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 76, 160, 24))
        content.addSubview_(self.pac_field)

        # --- Save/Cancel Buttons ---
        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(130, 20, 80, 30))
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(1)
        save_btn.setTarget_(self)
        save_btn.setAction_("savePreferences:")
        content.addSubview_(save_btn)

        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(220, 20, 80, 30))
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_("cancelPreferences:")
        content.addSubview_(cancel_btn)

        return self

    def run(self):
        self.center()
        self.makeKeyAndOrderFront_(None)

    def savePreferences_(self, sender):
        ws = os.path.expanduser("~/.susops")
        os.makedirs(ws, exist_ok=True)
        # write prefs with newline
        for name, field in (("ssh_host", self.ssh_field),
                            ("socks_port", self.socks_field),
                            ("pac_port", self.pac_field)):
            val = str(field.stringValue()) + "\n"
            with open(os.path.join(ws, name), "w") as f:
                f.write(val)
        rumps.notification("SusOps", "Preferences Saved", "Settings will apply on restart.")
        self.close()

    def cancelPreferences_(self, sender):
        self.close()

class SusOpsApp(rumps.App):
    def __init__(self):
        super(SusOpsApp, self).__init__(name="SusOps", quit_button=None)
        self._prefs_panel = None
        self.menu = [
            rumps.MenuItem("Start Proxy", callback=self.start_proxy),
            rumps.MenuItem("Stop Proxy", callback=self.stop_proxy),
            rumps.MenuItem("Restart Proxy", callback=self.restart_proxy),
            None,
            rumps.MenuItem("Add Host…", callback=self.add_host),
            rumps.MenuItem("Remove Host…", callback=self.remove_host),
            None,
            rumps.MenuItem("List Hosts", callback=self.list_hosts),
            None,
            rumps.MenuItem("Test Host…", callback=self.test_host),
            rumps.MenuItem("Test All", callback=self.test_all),
            None,
            rumps.MenuItem("Preferences…", callback=self.open_preferences),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]

    @staticmethod
    def _run_susops(command):
        shell = os.environ.get("SHELL", "/bin/bash")
        env_prefix = "env -u PYTHONSTARTUP -u PROMPT_COMMAND"
        full_cmd = f"{env_prefix} {shell} -ic 'susops {command}'"
        result = subprocess.run(full_cmd, shell=True, capture_output=True, encoding="utf-8", errors="ignore")
        if result.returncode != 0:
            rumps.alert(f"Error: {result.stderr.strip()}")
        return result.stdout.strip()

    @staticmethod
    def load_prefs():
        ws = os.path.expanduser("~/.susops")
        defaults = {"ssh_host": "pi", "socks_port": "1080", "pac_port": "1081"}
        prefs = {}
        for name in defaults:
            path = os.path.join(ws, name)
            try:
                with open(path) as f:
                    prefs[name] = f.read().strip()
            except IOError:
                prefs[name] = defaults[name]
        return prefs

    @staticmethod
    def alert_foreground(title, output):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        rumps.alert(title, output)

    @rumps.clicked("Start Proxy")
    def start_proxy(self, _):
        p = self.load_prefs()
        cmd = f"start {p['ssh_host']} {p['socks_port']} {p['pac_port']}"
        output = self._run_susops(cmd)
        rumps.notification("SusOps", "Start Proxy", output)

    @rumps.clicked("Stop Proxy")
    def stop_proxy(self, _):
        output = self._run_susops("stop")
        rumps.notification("SusOps", "Stop Proxy", output)

    @rumps.clicked("Restart Proxy")
    def restart_proxy(self, _):
        p = self.load_prefs()
        cmd = f"restart {p['ssh_host']} {p['socks_port']} {p['pac_port']}"
        output = self._run_susops(cmd)
        rumps.notification("SusOps", "Restart Proxy", output)

    @rumps.clicked("Add Host…")
    def add_host(self, _):
        host = rumps.Window("Enter hostname to add:", "SusOps: Add Host").run().text
        if host:
            output = self._run_susops(f"add {host}")
            rumps.notification("SusOps", "Add Host", output)

    @rumps.clicked("Remove Host…")
    def remove_host(self, _):
        host = rumps.Window("Enter hostname to remove:", "SusOps: Remove Host").run().text
        if host:
            output = self._run_susops(f"rm {host}")
            rumps.notification("SusOps", "Remove Host", output)

    @rumps.clicked("List Hosts")
    def list_hosts(self, _):
        output = self._run_susops("ls")
        self.alert_foreground("SusOps Hosts", output)

    @rumps.clicked("Test Host…")
    def test_host(self, _):
        host = rumps.Window("Enter hostname or port to test: ", "SusOps: Test Specific").run().text
        if host:
            # output = self._run_susops(f"test {host}")
            # rumps.alert("SusOps Test", output)
            result = self._run_susops(f"test {host}")
            alert = NSAlert.alloc().init()
            alert.setMessageText_("SusOps Test")
            # leave the official informativeText blank:
            alert.setInformativeText_("")
            # build a left-aligned text field
            tf = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 60))
            tf.setStringValue_(result)
            tf.setEditable_(False)
            tf.setDrawsBackground_(False)
            tf.setSelectable_(True)
            # ensure left alignment
            tf.cell().setAlignment_(0)  # 0 == NSLeftTextAlignment
            # plug it in and run
            alert.setAccessoryView_(tf)
            alert.addButtonWithTitle_("OK")
            alert.runModal()

    @rumps.clicked("Test All")
    def test_all(self, _):
        output = self._run_susops("test --all")
        self.alert_foreground("SusOps Test All", output)

    @rumps.clicked("Preferences…")
    def open_preferences(self, _):
        if self._prefs_panel is None:
            frame = NSMakeRect(0, 0, 320, 200)
            style = (
                    NSWindowStyleMaskTitled
                    | NSWindowStyleMaskClosable
                    | NSWindowStyleMaskResizable
            )
            self._prefs_panel = PrefsPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, style, NSBackingStoreBuffered, False
            )
        # load into fields
        prefs = self.load_prefs()
        self._prefs_panel.ssh_field.setStringValue_(prefs['ssh_host'])
        self._prefs_panel.socks_field.setStringValue_(prefs['socks_port'])
        self._prefs_panel.pac_field.setStringValue_(prefs['pac_port'])
        self._prefs_panel.run()

    @rumps.clicked("Quit")
    def quit_app(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    SusOpsApp().run()
