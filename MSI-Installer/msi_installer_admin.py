#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSI Batch-Installer  -  modernes Design, Hell/Dunkel umschaltbar
================================================================
- Menueleiste (Datei / Auswahl / Ansicht / Hilfe).
- Umschaltbares Farbschema: Hell <-> Dunkel per Knopf.
- Tabellarische Liste der MSI-Dateien mit Status-Spalte.
- Installiert mehrere MSI-Pakete nacheinander silent.
- Live-Mitlauf-Fenster, Fortschrittsbalken, Statusprotokoll.
- Pro MSI wird eine Log-Datei erzeugt.

Wichtiger Hinweis zu Admin-Rechten
----------------------------------
Dieses Programm verschafft sich KEINE Admin-Rechte selbst (kein PsExec,
kein geplanter Task). Es muss in einer Sitzung gestartet werden, die
bereits Admin-Rechte hat. Beim Start kann es sich per Windows-UAC-Abfrage
selbst als Administrator neu starten.

Voraussetzungen
---------------
- Windows
- Python 3.8 oder neuer (tkinter ist Teil der Standard-Installation)

Verwendung
----------
    python msi_installer_admin.py
"""

import os
import sys
import time
import ctypes
import queue
import threading
import subprocess
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ----------------------------------------------------------------------
# Grunddaten
# ----------------------------------------------------------------------
APP_NAME = "MSI Batch-Installer"
APP_VERSION = "4.0"

LOG_VERZEICHNIS = os.path.join(os.environ.get("TEMP", os.getcwd()),
                               "MSI-Installer-Logs")
os.makedirs(LOG_VERZEICHNIS, exist_ok=True)

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# ----------------------------------------------------------------------
# Farbschemata - Hell und Dunkel. Beide haben dieselben Schluessel.
# ----------------------------------------------------------------------
THEMES = {
    "hell": {
        "bg": "#eef1f6", "karte": "#ffffff",
        "akzent": "#3b5bdb", "akzent_hd": "#2f49b3",
        "kopf": "#3b5bdb", "kopf_text": "#ffffff", "kopf_sub": "#c7d2fe",
        "text": "#1f2937", "text_hell": "#6b7280",
        "ok": "#15803d", "fehler": "#dc2626", "warn": "#b45309",
        "aktiv": "#3b5bdb", "rahmen": "#d6dae3", "leiste": "#e2e6ee",
        "ok_bg": "#dcfce7", "warn_bg": "#fef3c7",
        "konsole_bg": "#0f172a", "konsole_fg": "#e2e8f0",
    },
    "dunkel": {
        "bg": "#0f1115", "karte": "#1a1d24",
        "akzent": "#5b78f0", "akzent_hd": "#7089f3",
        "kopf": "#1a1d24", "kopf_text": "#f1f5f9", "kopf_sub": "#94a3b8",
        "text": "#e5e7eb", "text_hell": "#9aa3b2",
        "ok": "#4ade80", "fehler": "#f87171", "warn": "#fbbf24",
        "aktiv": "#7089f3", "rahmen": "#2b2f3a", "leiste": "#15171d",
        "ok_bg": "#14321f", "warn_bg": "#3a2f12",
        "konsole_bg": "#0a0c10", "konsole_fg": "#cbd5e1",
    },
}


# ----------------------------------------------------------------------
# Admin-Pruefung / Neustart  (bewaehrte Logik, unveraendert)
# ----------------------------------------------------------------------
def ist_admin():
    """Prueft, ob der aktuelle Prozess Admin-Rechte besitzt."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:  # noqa: BLE001
        return False


def neu_starten_als_admin():
    """Startet dieses Skript neu - mit der Windows-UAC-Abfrage."""
    try:
        params = " ".join('"{0}"'.format(a) for a in sys.argv)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1)
        return rc > 32
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------------
# Installations-Logik  (bewaehrte Logik, unveraendert)
# ----------------------------------------------------------------------
def install_msi(msi_pfad, log_pfad, live_callback=None):
    """
    Installiert eine MSI silent. Setzt voraus, dass der aktuelle Prozess
    Admin-Rechte hat.  Rueckgabe: (erfolg: bool, meldung: str)

    live_callback: optionale Funktion, die mit jeder neuen Logzeile
    aufgerufen wird (fuer das Live-Mitlauf-Fenster).
    """
    msi_abs = os.path.abspath(msi_pfad)
    log_abs = os.path.abspath(log_pfad)

    if not os.path.isfile(msi_abs):
        return False, "MSI-Datei nicht gefunden"

    befehl = ('msiexec.exe /i "{0}" /qn /norestart /l*v "{1}"'
              .format(msi_abs, log_abs))

    try:
        proc = subprocess.Popen(befehl, creationflags=_NO_WINDOW)
    except Exception as exc:  # noqa: BLE001
        return False, "msiexec konnte nicht gestartet werden: " + str(exc)

    gelesen = 0
    start = time.time()
    while proc.poll() is None:
        if live_callback and os.path.isfile(log_abs):
            try:
                with open(log_abs, "r", encoding="utf-16-le",
                          errors="replace") as fh:
                    fh.seek(gelesen)
                    neu = fh.read()
                    gelesen = fh.tell()
                if neu.strip():
                    for zeile in neu.splitlines():
                        if zeile.strip():
                            live_callback(zeile.rstrip())
            except Exception:  # noqa: BLE001
                pass
        if time.time() - start > 3600:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
            return False, "Zeitueberschreitung (laenger als 1 Stunde)"
        time.sleep(0.4)

    rc = proc.returncode

    if rc == 0:
        return True, "Erfolgreich installiert"
    if rc == 3010:
        return True, "Installiert (Neustart erforderlich)"
    if rc == 1602:
        return False, "Vom Benutzer abgebrochen"
    if rc == 1603:
        return False, "Schwerwiegender Fehler bei der Installation (1603)"
    if rc == 1618:
        return False, "Andere Installation laeuft bereits (1618)"
    if rc == 1619:
        return False, "MSI-Paket konnte nicht geoeffnet werden (1619)"
    if rc == 1620:
        return False, "MSI-Paket ungueltig oder beschaedigt (1620)"
    if rc == 1625:
        return False, "Installation per Richtlinie gesperrt (1625)"
    if rc == 1639:
        return False, "Ungueltiges Argument (1639) - Pfad pruefen"
    if rc == 5:
        return False, "Zugriff verweigert (5) - Admin-Rechte fehlen?"
    return False, "Fehlercode {0} - Details im Log".format(rc)


# ----------------------------------------------------------------------
# Live-Mitlauf-Fenster
# ----------------------------------------------------------------------
class LiveFenster(tk.Toplevel):
    """Zweites Fenster, das die msiexec-Ausgabe in Echtzeit anzeigt."""

    def __init__(self, parent, theme):
        super().__init__(parent)
        self.theme = theme
        self.title("Installation - Live-Ansicht")
        self.geometry("760x440")
        self.minsize(560, 320)
        self.configure(bg=theme["karte"])
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self.kopf = tk.Frame(self, bg=theme["akzent"], height=46)
        self.kopf.pack(fill="x")
        self.kopf.pack_propagate(False)
        self.titel = tk.Label(self.kopf, text="Installation laeuft ...",
                              bg=theme["akzent"], fg="#ffffff",
                              font=("Segoe UI", 11, "bold"))
        self.titel.pack(side="left", padx=16)
        self.uhr = tk.Label(self.kopf, text="", bg=theme["akzent"],
                            fg="#dbeafe", font=("Segoe UI", 9))
        self.uhr.pack(side="right", padx=16)

        rahmen = tk.Frame(self, bg=theme["karte"])
        rahmen.pack(fill="both", expand=True, padx=12, pady=12)
        scroll = ttk.Scrollbar(rahmen, orient="vertical")
        self.text = tk.Text(rahmen, wrap="none", font=("Consolas", 8),
                            bg=theme["konsole_bg"], fg=theme["konsole_fg"],
                            insertbackground=theme["konsole_fg"],
                            relief="flat", borderwidth=0,
                            yscrollcommand=scroll.set, state="disabled")
        scroll.configure(command=self.text.yview)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        fuss = tk.Frame(self, bg=theme["karte"])
        fuss.pack(fill="x", padx=12, pady=(0, 12))
        self.autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(fuss, text="Automatisch nach unten scrollen",
                        variable=self.autoscroll).pack(side="left")
        ttk.Button(fuss, text="Leeren",
                   command=self._leeren).pack(side="right")

        self._start = time.time()
        self._aktiv = True
        self._uhr_aktualisieren()

    def _uhr_aktualisieren(self):
        if not self._aktiv:
            return
        sek = int(time.time() - self._start)
        self.uhr.configure(text="Laufzeit: {0:d}:{1:02d}".format(
            sek // 60, sek % 60))
        self.after(1000, self._uhr_aktualisieren)

    def neues_paket(self, name):
        self.titel.configure(text="Installiere:  " + name)
        self.zeile_anhaengen("")
        self.zeile_anhaengen("========== " + name + " ==========")

    def zeile_anhaengen(self, zeile):
        self.text.configure(state="normal")
        self.text.insert("end", zeile + "\n")
        if int(self.text.index("end-1c").split(".")[0]) > 5000:
            self.text.delete("1.0", "1000.0")
        if self.autoscroll.get():
            self.text.see("end")
        self.text.configure(state="disabled")

    def _leeren(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def fertig(self, erfolg, fehler):
        self._aktiv = False
        self.titel.configure(
            text="Fertig - {0} erfolgreich, {1} fehlgeschlagen".format(
                erfolg, fehler))
        self.zeile_anhaengen("")
        self.zeile_anhaengen(
            "===== ABGESCHLOSSEN: {0} erfolgreich, {1} fehlgeschlagen "
            "=====".format(erfolg, fehler))


# ----------------------------------------------------------------------
# Hauptanwendung
# ----------------------------------------------------------------------
class MsiInstallerApp:
    def __init__(self, root):
        self.root = root
        self.msi_dateien = []
        self.meldungs_queue = queue.Queue()
        self.laeuft = False
        self.admin = ist_admin()
        self.live_fenster = None

        self.theme_name = "hell"
        self.theme = THEMES[self.theme_name]

        self._fenster_einrichten()
        self._stil_einrichten()
        self._menue_bauen()
        self._oberflaeche_bauen()
        self._theme_anwenden()
        self._status_aktualisieren()
        self._admin_status_pruefen()

    # ---- Grundeinrichtung -------------------------------------------
    def _fenster_einrichten(self):
        self.root.title(APP_NAME)
        self.root.geometry("820x660")
        self.root.minsize(720, 580)

    def _stil_einrichten(self):
        self.stil = ttk.Style()
        try:
            self.stil.theme_use("clam")
        except tk.TclError:
            pass

    def _ttk_stil_aktualisieren(self):
        """Setzt die ttk-Styles passend zum aktuellen Theme."""
        t = self.theme
        s = self.stil

        s.configure("TFrame", background=t["bg"])
        s.configure("Karte.TFrame", background=t["karte"])
        s.configure("TLabel", background=t["bg"], foreground=t["text"],
                    font=("Segoe UI", 9))

        s.configure("TButton", font=("Segoe UI", 9), padding=7,
                    background=t["karte"], foreground=t["text"],
                    borderwidth=1, relief="flat")
        s.map("TButton",
              background=[("active", t["leiste"])],
              foreground=[("disabled", t["text_hell"])])

        s.configure("Akzent.TButton", font=("Segoe UI", 9, "bold"),
                    padding=9, foreground="#ffffff",
                    background=t["akzent"], borderwidth=0, relief="flat")
        s.map("Akzent.TButton",
              background=[("active", t["akzent_hd"]),
                          ("disabled", t["text_hell"])])

        s.configure("Treeview", font=("Segoe UI", 9), rowheight=28,
                    fieldbackground=t["karte"], background=t["karte"],
                    foreground=t["text"], borderwidth=0)
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                    background=t["leiste"], foreground=t["text"],
                    relief="flat")
        s.map("Treeview.Heading", background=[("active", t["leiste"])])
        s.map("Treeview",
              background=[("selected", t["akzent"])],
              foreground=[("selected", "#ffffff")])

        s.configure("TProgressbar", troughcolor=t["leiste"],
                    background=t["akzent"], borderwidth=0, thickness=10)
        s.configure("TScrollbar", background=t["leiste"],
                    troughcolor=t["bg"], borderwidth=0)
        s.configure("TCheckbutton", background=t["karte"],
                    foreground=t["text"], font=("Segoe UI", 9))
        s.map("TCheckbutton", background=[("active", t["karte"])])

    # ---- Menueleiste -------------------------------------------------
    def _menue_bauen(self):
        menue = tk.Menu(self.root)

        m_datei = tk.Menu(menue, tearoff=0)
        m_datei.add_command(label="MSI-Dateien hinzufuegen...",
                            accelerator="Strg+O",
                            command=self.dateien_hinzufuegen)
        m_datei.add_command(label="Ordner hinzufuegen...",
                            command=self.ordner_hinzufuegen)
        m_datei.add_separator()
        m_datei.add_command(label="Live-Ansicht anzeigen",
                            command=self.live_ansicht_zeigen)
        m_datei.add_command(label="Log-Ordner oeffnen",
                            command=self.log_ordner_oeffnen)
        m_datei.add_separator()
        m_datei.add_command(label="Beenden", accelerator="Strg+Q",
                            command=self.beenden)
        menue.add_cascade(label="Datei", menu=m_datei)

        m_auswahl = tk.Menu(menue, tearoff=0)
        m_auswahl.add_command(label="Alle auswaehlen",
                              command=lambda: self._alle_setzen(True))
        m_auswahl.add_command(label="Auswahl aufheben",
                              command=lambda: self._alle_setzen(False))
        m_auswahl.add_separator()
        m_auswahl.add_command(label="Markierte entfernen",
                              command=self.markierte_entfernen)
        m_auswahl.add_command(label="Liste leeren",
                              command=self.liste_leeren)
        menue.add_cascade(label="Auswahl", menu=m_auswahl)

        m_ansicht = tk.Menu(menue, tearoff=0)
        m_ansicht.add_command(label="Helles Design",
                              command=lambda: self.theme_setzen("hell"))
        m_ansicht.add_command(label="Dunkles Design",
                              command=lambda: self.theme_setzen("dunkel"))
        m_ansicht.add_separator()
        m_ansicht.add_command(label="Design umschalten",
                              accelerator="Strg+D",
                              command=self.theme_umschalten)
        menue.add_cascade(label="Ansicht", menu=m_ansicht)

        m_hilfe = tk.Menu(menue, tearoff=0)
        m_hilfe.add_command(label="Hinweise zur Verwendung",
                            command=self.hilfe_anzeigen)
        m_hilfe.add_command(label="Ueber " + APP_NAME,
                            command=self.ueber_anzeigen)
        menue.add_cascade(label="Hilfe", menu=m_hilfe)

        self.root.config(menu=menue)
        self.root.bind("<Control-o>", lambda e: self.dateien_hinzufuegen())
        self.root.bind("<Control-q>", lambda e: self.beenden())
        self.root.bind("<Control-d>", lambda e: self.theme_umschalten())

    # ---- Oberflaeche -------------------------------------------------
    def _oberflaeche_bauen(self):
        self.kopf = tk.Frame(self.root, height=70)
        self.kopf.pack(fill="x")
        self.kopf.pack_propagate(False)

        kopf_links = tk.Frame(self.kopf)
        kopf_links.pack(side="left", fill="y", padx=22)
        self.kopf_titel = tk.Label(kopf_links, text="\U0001F4E6  " + APP_NAME,
                                   font=("Segoe UI", 16, "bold"))
        self.kopf_titel.pack(anchor="w", pady=(14, 0))
        self.kopf_sub = tk.Label(
            kopf_links,
            text="Mehrere MSI-Pakete nacheinander installieren",
            font=("Segoe UI", 9))
        self.kopf_sub.pack(anchor="w")

        self.theme_knopf = tk.Button(
            self.kopf, text="\U0001F319  Dunkel", relief="flat",
            font=("Segoe UI", 9, "bold"), cursor="hand2", bd=0,
            padx=14, pady=6, command=self.theme_umschalten)
        self.theme_knopf.pack(side="right", padx=20)

        self.inhalt = ttk.Frame(self.root, padding=16)
        self.inhalt.pack(fill="both", expand=True)

        self.hinweis = tk.Label(self.inhalt, text="", anchor="w",
                                font=("Segoe UI", 9, "bold"),
                                padx=12, pady=7)
        self.hinweis.pack(fill="x", pady=(0, 12))

        werkzeug = ttk.Frame(self.inhalt)
        werkzeug.pack(fill="x", pady=(0, 10))
        ttk.Button(werkzeug, text="\u2795  MSI hinzufuegen",
                   command=self.dateien_hinzufuegen).pack(side="left")
        ttk.Button(werkzeug, text="\U0001F4C1  Ordner",
                   command=self.ordner_hinzufuegen).pack(side="left", padx=(6, 0))
        ttk.Button(werkzeug, text="\u2714  Alle",
                   command=lambda: self._alle_setzen(True)).pack(side="left", padx=(6, 0))
        ttk.Button(werkzeug, text="\u2716  Keine",
                   command=lambda: self._alle_setzen(False)).pack(side="left", padx=(6, 0))
        ttk.Button(werkzeug, text="\U0001F5D1  Entfernen",
                   command=self.markierte_entfernen).pack(side="left", padx=(6, 0))

        tabellen_rahmen = ttk.Frame(self.inhalt)
        tabellen_rahmen.pack(fill="both", expand=True)

        spalten = ("auswahl", "name", "status")
        self.tabelle = ttk.Treeview(tabellen_rahmen, columns=spalten,
                                    show="headings", selectmode="extended")
        self.tabelle.heading("auswahl", text="\u2713")
        self.tabelle.heading("name", text="MSI-Datei")
        self.tabelle.heading("status", text="Status")
        self.tabelle.column("auswahl", width=46, anchor="center", stretch=False)
        self.tabelle.column("name", width=440, anchor="w")
        self.tabelle.column("status", width=240, anchor="w")

        scroll = ttk.Scrollbar(tabellen_rahmen, orient="vertical",
                               command=self.tabelle.yview)
        self.tabelle.configure(yscrollcommand=scroll.set)
        self.tabelle.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tabelle.bind("<Button-1>", self._tabelle_klick)

        self.protokoll_titel = ttk.Label(self.inhalt, text="Statusprotokoll",
                                         font=("Segoe UI", 9, "bold"))
        self.protokoll_titel.pack(anchor="w", pady=(14, 4))
        self.protokoll = tk.Text(self.inhalt, height=7, state="disabled",
                                 wrap="word", font=("Consolas", 9),
                                 relief="flat", borderwidth=1,
                                 highlightthickness=1)
        self.protokoll.pack(fill="x")

        unten = ttk.Frame(self.inhalt)
        unten.pack(fill="x", pady=(14, 0))
        self.fortschritt = ttk.Progressbar(unten, mode="determinate")
        self.fortschritt.pack(side="left", fill="x", expand=True,
                              padx=(0, 12), ipady=2)
        self.start_knopf = ttk.Button(unten, text="\u25B6  Installation starten",
                                      style="Akzent.TButton",
                                      command=self.installation_starten)
        self.start_knopf.pack(side="right")
        self.beenden_knopf = ttk.Button(unten, text="\u2715  Beenden",
                                        command=self.beenden)
        self.beenden_knopf.pack(side="right", padx=(0, 8))

        self.statusleiste = tk.Label(self.root, text="", anchor="w",
                                     font=("Segoe UI", 8), padx=10, pady=3)
        self.statusleiste.pack(fill="x", side="bottom")

        self.fusszeile = tk.Frame(self.root, height=26)
        self.fusszeile.pack(fill="x", side="bottom")
        self.fusszeile.pack_propagate(False)
        self.fuss_links = tk.Label(
            self.fusszeile,
            text="{0}  \u00b7  Version {1}".format(APP_NAME, APP_VERSION),
            font=("Segoe UI", 8))
        self.fuss_links.pack(side="left", padx=10)
        self.fuss_rechts = tk.Label(self.fusszeile,
                                    text="Logs: " + LOG_VERZEICHNIS,
                                    font=("Segoe UI", 8))
        self.fuss_rechts.pack(side="right", padx=10)

    # ---- Theme-Verwaltung -------------------------------------------
    def theme_umschalten(self):
        self.theme_setzen("dunkel" if self.theme_name == "hell" else "hell")

    def theme_setzen(self, name):
        if name not in THEMES:
            return
        self.theme_name = name
        self.theme = THEMES[name]
        self._theme_anwenden()

    def _theme_anwenden(self):
        """Faerbt die gesamte Oberflaeche nach dem aktuellen Theme."""
        t = self.theme
        self._ttk_stil_aktualisieren()
        self.root.configure(bg=t["bg"])

        self.kopf.configure(bg=t["kopf"])
        for w in self.kopf.winfo_children():
            try:
                w.configure(bg=t["kopf"])
            except tk.TclError:
                pass
        self.kopf_titel.configure(bg=t["kopf"], fg=t["kopf_text"])
        self.kopf_sub.configure(bg=t["kopf"], fg=t["kopf_sub"])

        if self.theme_name == "hell":
            self.theme_knopf.configure(text="\U0001F319  Dunkel")
        else:
            self.theme_knopf.configure(text="\u2600  Hell")
        self.theme_knopf.configure(bg=t["akzent"], fg="#ffffff",
                                   activebackground=t["akzent_hd"],
                                   activeforeground="#ffffff")

        self.protokoll.configure(bg=t["karte"], fg=t["text"],
                                 highlightbackground=t["rahmen"],
                                 highlightcolor=t["rahmen"],
                                 insertbackground=t["text"])

        self.statusleiste.configure(bg=t["leiste"], fg=t["text_hell"])
        self.fusszeile.configure(bg=t["karte"])
        self.fuss_links.configure(bg=t["karte"], fg=t["text_hell"])
        self.fuss_rechts.configure(bg=t["karte"], fg=t["text_hell"])

        self.tabelle.tag_configure("ok", foreground=t["ok"])
        self.tabelle.tag_configure("fehler", foreground=t["fehler"])
        self.tabelle.tag_configure("aktiv", foreground=t["aktiv"])

        self._admin_hinweis_faerben()

        if self.live_fenster and self.live_fenster.winfo_exists():
            try:
                self.live_fenster.configure(bg=t["karte"])
                self.live_fenster.text.configure(bg=t["konsole_bg"],
                                                 fg=t["konsole_fg"])
            except tk.TclError:
                pass

    # ---- Admin-Status ------------------------------------------------
    def _admin_status_pruefen(self):
        self._admin_hinweis_faerben()
        if not self.admin:
            self.start_knopf.configure(state="disabled")
            self.root.after(300, self._neustart_anbieten)

    def _admin_hinweis_faerben(self):
        t = self.theme
        if self.admin:
            self.hinweis.configure(
                text="\u2714  Admin-Rechte vorhanden - Installation moeglich.",
                bg=t["ok_bg"], fg=t["ok"])
        else:
            self.hinweis.configure(
                text="\u26A0  Keine Admin-Rechte. Bitte das Programm als "
                     "Administrator neu starten.",
                bg=t["warn_bg"], fg=t["warn"])

    def _neustart_anbieten(self):
        if messagebox.askyesno(
                APP_NAME,
                "Dieses Programm hat keine Admin-Rechte.\n\n"
                "Ohne Admin-Rechte koennen MSI-Pakete nicht installiert\n"
                "werden.\n\n"
                "Jetzt als Administrator neu starten?"):
            if neu_starten_als_admin():
                self.root.destroy()
            else:
                messagebox.showwarning(
                    APP_NAME,
                    "Der Neustart als Administrator wurde abgebrochen\n"
                    "oder ist fehlgeschlagen.")

    # ---- Datei-Verwaltung -------------------------------------------
    def dateien_hinzufuegen(self):
        pfade = filedialog.askopenfilenames(
            title="MSI-Dateien auswaehlen",
            filetypes=[("Windows Installer", "*.msi")])
        self._dateien_uebernehmen(pfade)

    def ordner_hinzufuegen(self):
        ordner = filedialog.askdirectory(title="Ordner mit MSI-Dateien waehlen")
        if not ordner:
            return
        gefunden = [
            os.path.join(ordner, f) for f in sorted(os.listdir(ordner))
            if f.lower().endswith(".msi")
        ]
        if not gefunden:
            messagebox.showinfo(APP_NAME,
                                "In diesem Ordner wurden keine MSI-Dateien "
                                "gefunden.")
            return
        self._dateien_uebernehmen(gefunden)

    def _dateien_uebernehmen(self, pfade):
        neu = 0
        for pfad in pfade:
            if pfad not in self.msi_dateien:
                self.msi_dateien.append(pfad)
                self.tabelle.insert(
                    "", "end", iid=pfad,
                    values=("\u2611", os.path.basename(pfad), "Bereit"))
                neu += 1
        if neu:
            self._protokoll("{0} Datei(en) hinzugefuegt.".format(neu))
        self._status_aktualisieren()

    def liste_leeren(self):
        if self.laeuft:
            return
        self.msi_dateien.clear()
        for iid in self.tabelle.get_children():
            self.tabelle.delete(iid)
        self._status_aktualisieren()

    def markierte_entfernen(self):
        if self.laeuft:
            return
        for iid in self.tabelle.selection():
            if iid in self.msi_dateien:
                self.msi_dateien.remove(iid)
            self.tabelle.delete(iid)
        self._status_aktualisieren()

    def _tabelle_klick(self, event):
        if self.laeuft:
            return
        if self.tabelle.identify_region(event.x, event.y) != "cell":
            return
        if self.tabelle.identify_column(event.x) != "#1":
            return
        iid = self.tabelle.identify_row(event.y)
        if iid:
            werte = list(self.tabelle.item(iid, "values"))
            werte[0] = "\u2610" if werte[0] == "\u2611" else "\u2611"
            self.tabelle.item(iid, values=werte)
            self._status_aktualisieren()

    def _alle_setzen(self, wert):
        symbol = "\u2611" if wert else "\u2610"
        for iid in self.tabelle.get_children():
            werte = list(self.tabelle.item(iid, "values"))
            werte[0] = symbol
            self.tabelle.item(iid, values=werte)
        self._status_aktualisieren()

    def _ausgewaehlte_pfade(self):
        return [iid for iid in self.tabelle.get_children()
                if self.tabelle.item(iid, "values")[0] == "\u2611"]

    # ---- Anzeige -----------------------------------------------------
    def _protokoll(self, text):
        zeit = datetime.now().strftime("%H:%M:%S")
        self.protokoll.configure(state="normal")
        self.protokoll.insert("end", "[{0}]  {1}\n".format(zeit, text))
        self.protokoll.see("end")
        self.protokoll.configure(state="disabled")

    def _status_aktualisieren(self):
        gesamt = len(self.tabelle.get_children())
        gewaehlt = len(self._ausgewaehlte_pfade())
        self.statusleiste.configure(
            text="  {0} Datei(en) in der Liste  -  {1} ausgewaehlt".format(
                gesamt, gewaehlt))

    def _tabellen_status(self, iid, text, tag=""):
        werte = list(self.tabelle.item(iid, "values"))
        werte[2] = text
        self.tabelle.item(iid, values=werte, tags=(tag,) if tag else ())

    # ---- Installation ------------------------------------------------
    def installation_starten(self):
        if self.laeuft:
            return
        if not self.admin:
            messagebox.showwarning(
                APP_NAME,
                "Das Programm hat keine Admin-Rechte.\n"
                "Bitte als Administrator neu starten.")
            return

        ausgewaehlt = self._ausgewaehlte_pfade()
        if not ausgewaehlt:
            messagebox.showwarning(APP_NAME,
                                   "Bitte mindestens eine MSI auswaehlen.")
            return

        if not messagebox.askyesno(
                APP_NAME,
                "{0} Programm(e) werden jetzt installiert.\n\n"
                "Fortfahren?".format(len(ausgewaehlt))):
            return

        self.laeuft = True
        self.start_knopf.configure(state="disabled",
                                   text="\u23F3  Installation laeuft...")
        self.fortschritt.configure(maximum=len(ausgewaehlt), value=0)
        self._protokoll("=== Installation gestartet: {0} Datei(en) ===".format(
            len(ausgewaehlt)))
        for iid in ausgewaehlt:
            self._tabellen_status(iid, "Wartet ...")

        self.live_fenster = LiveFenster(self.root, self.theme)

        threading.Thread(
            target=self._installations_lauf,
            args=(ausgewaehlt,),
            daemon=True,
        ).start()
        self.root.after(200, self._queue_pruefen)

    def _installations_lauf(self, dateien):
        erfolg = fehler = 0
        for index, msi in enumerate(dateien, start=1):
            name = os.path.basename(msi)
            self.meldungs_queue.put(("aktiv", msi, "Installiere ..."))
            self.meldungs_queue.put(("log", None,
                                     "Installiere ({0}/{1}): {2}".format(
                                         index, len(dateien), name)))

            if not os.path.isfile(msi):
                fehler += 1
                self.meldungs_queue.put(("fehler", msi, "Datei nicht gefunden"))
                self.meldungs_queue.put(("log", None,
                                         "  [FEHLER] " + name +
                                         " - Datei nicht gefunden"))
                self.meldungs_queue.put(("fortschritt", None, index))
                continue

            stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_pfad = os.path.join(LOG_VERZEICHNIS,
                                    "{0}_{1}.log".format(name, stempel))

            def _live(zeile, _name=name):
                self.meldungs_queue.put(("live", None, (_name, zeile)))

            self.meldungs_queue.put(("live_titel", None, name))

            ok, meldung = install_msi(msi, log_pfad, live_callback=_live)
            versuche = 1
            while (not ok and "1618" in meldung and versuche < 3):
                self.meldungs_queue.put((
                    "aktiv", msi, "Wartet auf anderen Installer ..."))
                self.meldungs_queue.put((
                    "log", None,
                    "  Hinweis: anderer Installer aktiv - "
                    "warte 15 Sek. und versuche erneut ..."))
                time.sleep(15)
                ok, meldung = install_msi(msi, log_pfad, live_callback=_live)
                versuche += 1

            if ok:
                erfolg += 1
                self.meldungs_queue.put(("ok", msi, meldung))
                self.meldungs_queue.put(("log", None, "  [OK] " + name))
            else:
                fehler += 1
                self.meldungs_queue.put(("fehler", msi, meldung))
                self.meldungs_queue.put(("log", None,
                                         "  [FEHLER] " + name + " - " + meldung))

            self.meldungs_queue.put(("fortschritt", None, index))
            time.sleep(2)

        self.meldungs_queue.put(("fertig", None, (erfolg, fehler)))

    def _queue_pruefen(self):
        try:
            while True:
                art, iid, daten = self.meldungs_queue.get_nowait()
                if art == "aktiv":
                    self._tabellen_status(iid, daten, "aktiv")
                elif art == "ok":
                    self._tabellen_status(iid, "\u2714 " + daten, "ok")
                elif art == "fehler":
                    self._tabellen_status(iid, "\u2716 " + daten, "fehler")
                elif art == "log":
                    self._protokoll(daten)
                elif art == "fortschritt":
                    self.fortschritt.configure(value=daten)
                elif art == "live_titel":
                    if self.live_fenster:
                        self.live_fenster.neues_paket(daten)
                elif art == "live":
                    if self.live_fenster:
                        _, zeile = daten
                        self.live_fenster.zeile_anhaengen(zeile)
                elif art == "fertig":
                    erfolg, fehler = daten
                    self._abschluss(erfolg, fehler)
                    return
        except queue.Empty:
            pass
        self.root.after(200, self._queue_pruefen)

    def _abschluss(self, erfolg, fehler):
        self.laeuft = False
        self.start_knopf.configure(state="normal",
                                   text="\u25B6  Installation starten")
        self._protokoll("=== Fertig: {0} erfolgreich, {1} fehlgeschlagen "
                         "===".format(erfolg, fehler))
        if self.live_fenster:
            self.live_fenster.fertig(erfolg, fehler)
        messagebox.showinfo(
            APP_NAME + " - Ergebnis",
            "Erfolgreich: {0}\nFehlgeschlagen: {1}\n\n"
            "Log-Dateien:\n{2}".format(erfolg, fehler, LOG_VERZEICHNIS))

    # ---- Menue-Aktionen ---------------------------------------------
    def beenden(self):
        if self.laeuft:
            if not messagebox.askyesno(
                    APP_NAME,
                    "Es laeuft gerade eine Installation.\n"
                    "Trotzdem beenden?"):
                return
        self.root.quit()

    def live_ansicht_zeigen(self):
        if self.live_fenster and self.live_fenster.winfo_exists():
            self.live_fenster.deiconify()
            self.live_fenster.lift()
        else:
            messagebox.showinfo(
                APP_NAME,
                "Die Live-Ansicht oeffnet sich automatisch, sobald\n"
                "eine Installation gestartet wird.")

    def log_ordner_oeffnen(self):
        try:
            os.startfile(LOG_VERZEICHNIS)
        except Exception:  # noqa: BLE001
            messagebox.showinfo(APP_NAME, "Log-Ordner:\n" + LOG_VERZEICHNIS)

    def hilfe_anzeigen(self):
        messagebox.showinfo(
            "Hinweise zur Verwendung",
            "Dieses Programm installiert MSI-Pakete - es braucht dafuer\n"
            "Admin-Rechte und kann sich diese NICHT selbst verschaffen.\n\n"
            "So startest du es mit Admin-Rechten:\n"
            "- Als lokaler Administrator am Rechner anmelden, ODER\n"
            "- Eine Eingabeaufforderung 'Als Administrator ausfuehren'\n"
            "  oeffnen und darin starten.\n\n"
            "Ablauf:\n"
            "1. MSI-Dateien oder einen Ordner hinzufuegen.\n"
            "2. In der Tabelle auswaehlen, was installiert werden soll.\n"
            "3. 'Installation starten'.\n\n"
            "Das Design laesst sich oben rechts oder mit Strg+D\n"
            "zwischen Hell und Dunkel umschalten.\n\n"
            "Logs liegen unter:\n  " + LOG_VERZEICHNIS)

    def ueber_anzeigen(self):
        messagebox.showinfo(
            "Ueber " + APP_NAME,
            APP_NAME + "  Version " + APP_VERSION + "\n\n"
            "Installiert mehrere MSI-Pakete nacheinander silent.\n"
            "Mit Live-Ansicht und umschaltbarem Hell/Dunkel-Design.\n\n"
            "Das Programm muss in einer Sitzung mit Admin-Rechten\n"
            "laufen - es umgeht die Windows-Rechteverwaltung nicht.")


# ----------------------------------------------------------------------
# Start
# ----------------------------------------------------------------------
def main():
    if os.name != "nt":
        print("Dieses Programm laeuft nur unter Windows.")
        sys.exit(1)

    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass

    app = MsiInstallerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.beenden)
    root.mainloop()


if __name__ == "__main__":
    main()
