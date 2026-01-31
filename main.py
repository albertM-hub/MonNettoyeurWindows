import customtkinter as ctk
import winshell
import os
import shutil
import hashlib
import psutil
import platform
import winreg
import subprocess
from tkinter import filedialog, messagebox
from datetime import datetime

ctk.set_appearance_mode("dark") 
ctk.set_default_color_theme("green") 

class CleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mon Compagnon de Nettoyage Pro - V1.2")
        self.geometry("950x980")
        
        self.selected_folder = ""
        self.tools_folder = "" # Dossier spécifique pour le scan Top 20
        self.files_to_delete = []
        self.apps_data = {}
        self.preview_win = None

        # --- SYSTÈME D'ONGLETS ---
        self.tabview = ctk.CTkTabview(self, width=900, height=880, fg_color="#2B2B2B")
        self.tabview.pack(pady=10, padx=20)
        
        self.tab_clean = self.tabview.add("Nettoyage")
        self.tab_tools = self.tabview.add("Outils & Système")
        self.tab_apps = self.tabview.add("Programmes")
        self.tab_help = self.tabview.add("Mode d'emploi")

        self.setup_clean_tab()
        self.setup_tools_tab()
        self.setup_apps_tab()
        self.setup_help_tab()

    # --- ONGLET NETTOYAGE ---
    def setup_clean_tab(self):
        ctk.CTkLabel(self.tab_clean, text="🛡️ Maintenance des Fichiers", font=("Segoe UI", 26, "bold"), text_color="#FFCC70").pack(pady=15)
        
        f_frame = ctk.CTkFrame(self.tab_clean, fg_color="#333333", corner_radius=15)
        f_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkButton(f_frame, text="📁 1. CHOISIR LE DOSSIER CIBLE", fg_color="#D35400", hover_color="#E67E22", command=self.browse_folder).pack(pady=15)
        self.path_label = ctk.CTkLabel(f_frame, text="Aucune cible sélectionnée", font=("Segoe UI", 12, "italic"))
        self.path_label.pack(pady=5)

        self.exclude_entry = ctk.CTkEntry(self.tab_clean, placeholder_text="Protéger des mots-clés (ex: perso, travail)...", width=650, height=40)
        self.exclude_entry.pack(pady=15)

        opt_frame = ctk.CTkFrame(self.tab_clean, fg_color="transparent")
        opt_frame.pack(pady=10, fill="both")
        
        self.vars = {
            "temp": ctk.BooleanVar(value=True),
            "docs": ctk.BooleanVar(value=False),
            "music": ctk.BooleanVar(value=False),
            "video": ctk.BooleanVar(value=False),
            "dupes": ctk.BooleanVar(value=False)
        }
        
        self.add_check(opt_frame, "🗑️ Nettoyer Corbeille et Fichiers Temporaires", "temp")
        self.add_check(opt_frame, "📄 Scanner et Supprimer Docs / XML", "docs")
        self.add_check(opt_frame, "🎵 Scanner et Supprimer Musiques", "music")
        self.add_check(opt_frame, "🎬 Scanner et Supprimer Vidéos", "video")
        self.add_check(opt_frame, "👥 Rechercher les DOUBLONS (MD5)", "dupes")

        self.progress = ctk.CTkProgressBar(self.tab_clean, width=700, progress_color="#FFCC70")
        self.progress.set(0)
        self.progress.pack(pady=25)

        ctk.CTkButton(self.tab_clean, text="🔍 2. ANALYSER L'ESPACE", fg_color="#5D6D7E", width=200, height=45, command=self.run_preview).pack(pady=10)
        ctk.CTkButton(self.tab_clean, text="🚀 3. LANCER LE NETTOYAGE", fg_color="#E67E22", height=55, font=("Segoe UI", 16, "bold"), command=self.start_cleaning).pack(pady=10)
        
        self.status_label = ctk.CTkLabel(self.tab_clean, text="Prêt", text_color="#AAAAAA")
        self.status_label.pack()

    def add_check(self, master, text, var):
        ctk.CTkCheckBox(master, text=text, variable=self.vars[var], font=("Segoe UI", 13), checkmark_color="#FFCC70", fg_color="#E67E22").pack(pady=6, padx=80, anchor="w")

    # --- ONGLET OUTILS & SYSTÈME ---
    def setup_tools_tab(self):
        # --- Diagnostic Système ---
        ctk.CTkLabel(self.tab_tools, text="📊 Diagnostic Système", font=("Segoe UI", 24, "bold"), text_color="#FFCC70").pack(pady=15)
        
        self.diag_frame = ctk.CTkFrame(self.tab_tools, fg_color="#1E1E1E", corner_radius=15)
        self.diag_frame.pack(pady=10, padx=20, fill="x")
        
        self.info_label = ctk.CTkLabel(self.diag_frame, text="Cliquez sur 'Actualiser' pour voir les détails", font=("Consolas", 12), justify="left")
        self.info_label.pack(pady=20, padx=20)
        
        ctk.CTkButton(self.tab_tools, text="🔄 ACTUALISER LES INFOS PC", fg_color="#273746", command=self.show_system_info).pack(pady=5)

        # --- Top 20 Fichiers Lourds ---
        ctk.CTkLabel(self.tab_tools, text="📂 Analyse des Gros Fichiers", font=("Segoe UI", 24, "bold"), text_color="#FFCC70").pack(pady=(30, 5))
        
        tools_btn_frame = ctk.CTkFrame(self.tab_tools, fg_color="transparent")
        tools_btn_frame.pack(pady=10)
        
        ctk.CTkButton(tools_btn_frame, text="📁 Choisir Dossier/Disque", fg_color="#2980B9", command=self.browse_tools_folder).pack(side="left", padx=10)
        ctk.CTkButton(tools_btn_frame, text="🔎 Scanner", fg_color="#E67E22", command=self.find_large_files).pack(side="left", padx=10)

        self.tools_path_label = ctk.CTkLabel(self.tab_tools, text="Aucun dossier sélectionné", font=("Segoe UI", 11, "italic"))
        self.tools_path_label.pack()

        self.large_files_box = ctk.CTkTextbox(self.tab_tools, width=800, height=280, fg_color="#1E1E1E", font=("Consolas", 12))
        self.large_files_box.pack(pady=10, padx=20)

    # --- ONGLET MODE D'EMPLOI (NOUVEAU DESIGN) ---
    def setup_help_tab(self):
        scroll_help = ctk.CTkScrollableFrame(self.tab_help, width=800, height=800, fg_color="transparent")
        scroll_help.pack(pady=10, padx=10, fill="both", expand=True)

        sections = [
            ("🛡️ SÉCURITÉ AVANT TOUT", "L'analyse (Étape 2) est obligatoire. Elle vous montre la liste des fichiers avant d'effacer quoi que ce soit. Rien n'est supprimé sans votre clic final sur 'Lancer le nettoyage'."),
            ("👥 LES DOUBLONS", "Le programme compare le contenu réel des fichiers (MD5). L'original est TOUJOURS conservé, seules les copies sont listées pour suppression."),
            ("📂 OUTILS DE DIAGNOSTIC", "L'onglet Outils vous permet de voir l'état de votre RAM et de votre processeur, ainsi que de débusquer les fichiers qui saturent votre disque."),
            ("📦 GESTION DES APPS", "Pour désinstaller un programme, copiez son nom dans la barre rouge. Cela lance la procédure officielle de Windows pour un retrait propre."),
            ("📝 RAPPORTS", "Après chaque nettoyage, un fichier 'Rapport_Nettoyage_Pro.txt' est créé sur votre bureau pour garder une trace de chaque action.")
        ]

        for title, content in sections:
            lbl_title = ctk.CTkLabel(scroll_help, text=title, font=("Segoe UI", 18, "bold"), text_color="#E67E22")
            lbl_title.pack(pady=(15, 5), padx=20, anchor="w")
            lbl_content = ctk.CTkLabel(scroll_help, text=content, font=("Segoe UI", 13), wraplength=750, justify="left")
            lbl_content.pack(pady=(0, 10), padx=30, anchor="w")
            ctk.CTkFrame(scroll_help, height=2, fg_color="#444444").pack(fill="x", padx=20)

    # --- LOGIQUE SYSTÈME ---
    def show_system_info(self):
        disk = psutil.disk_usage('C:')
        info = (
            f"💻 SYSTÈME  : {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"🏠 NOM PC   : {platform.node()}\n"
            f"🧠 CPU      : {platform.processor()}\n"
            f"⚙️ CŒURS    : {psutil.cpu_count(logical=False)} Physiques / {psutil.cpu_count(logical=True)} Logiques\n"
            f"----------------------------------------------------------\n"
            f"⚡ RAM TOTALE : {round(psutil.virtual_memory().total / (1024**3), 2)} Go\n"
            f"🔥 RAM UTILISÉE : {psutil.virtual_memory().percent}%\n"
            f"----------------------------------------------------------\n"
            f"💾 DISQUE C: : {round(disk.total / (1024**3), 2)} Go au total\n"
            f"🟢 LIBRE     : {round(disk.free / (1024**3), 2)} Go restants\n"
            f"📊 OCCUPATION: {disk.percent}%"
        )
        self.info_label.configure(text=info, text_color="#FFCC70")

    def browse_tools_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.tools_folder = folder
            self.tools_path_label.configure(text=f"Cible scan : {folder}", text_color="#FFCC70")

    def find_large_files(self):
        target = self.tools_folder if self.tools_folder else self.selected_folder
        if not target:
            messagebox.showwarning("Cible", "Veuillez choisir un dossier à scanner.")
            return
        
        self.large_files_box.delete("0.0", "end")
        self.large_files_box.insert("end", "Scan en cours... patientez.\n\n")
        self.update()
        
        file_list = []
        for root, _, files in os.walk(target):
            for f in files:
                p = os.path.join(root, f)
                try: file_list.append((p, os.path.getsize(p)))
                except: continue
        
        file_list.sort(key=lambda x: x[1], reverse=True)
        self.large_files_box.delete("0.0", "end")
        
        for i, (p, s) in enumerate(file_list[:20]):
            size_str = f"{round(s/(1024**3), 2)} Go" if s >= 1024**3 else f"{round(s/(1024**2), 2)} Mo"
            line = f"[{size_str}] -> {os.path.basename(p)}\n"
            
            # On met le premier en gras/rouge (visuellement géré par l'ordre ici)
            if i == 0:
                self.large_files_box.insert("end", "🔥 LE PLUS GROS : " + line)
            else:
                self.large_files_box.insert("end", f"{i+1}. {line}")

    # --- RESTE DU CODE (SÉLECTION, SCAN, NETTOYAGE) ---
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder = folder
            self.path_label.configure(text=f"Cible : {folder}", text_color="#FFCC70")

    def setup_apps_tab(self):
        ctk.CTkLabel(self.tab_apps, text="📦 Gestion des Logiciels", font=("Segoe UI", 22, "bold"), text_color="#FFCC70").pack(pady=15)
        uninst_frame = ctk.CTkFrame(self.tab_apps, fg_color="#333333")
        uninst_frame.pack(pady=10, padx=20, fill="x")
        self.app_to_remove = ctk.CTkEntry(uninst_frame, placeholder_text="Copiez le nom exact du programme ici...", width=450)
        self.app_to_remove.pack(side="left", padx=10, pady=15)
        ctk.CTkButton(uninst_frame, text="DÉSINSTALLER", fg_color="#E74C3C", command=self.uninstall_app).pack(side="left", padx=10)
        self.app_listbox = ctk.CTkTextbox(self.tab_apps, width=750, height=480)
        self.app_listbox.pack(pady=10, padx=20)
        ctk.CTkButton(self.tab_apps, text="🔄 Actualiser la liste", command=self.list_installed_apps).pack(pady=10)

    def list_installed_apps(self):
        self.app_listbox.delete("0.0", "end")
        self.apps_data = {}
        path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            sub = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub) as sk:
                                name = winreg.QueryValueEx(sk, "DisplayName")[0]
                                try: cmd = winreg.QueryValueEx(sk, "UninstallString")[0]
                                except: cmd = ""
                                self.apps_data[name.lower()] = cmd
                                self.app_listbox.insert("end", f"• {name}\n")
                        except: continue
            except: continue

    def uninstall_app(self):
        name = self.app_to_remove.get().lower().strip()
        if name in self.apps_data and self.apps_data[name]:
            if messagebox.askyesno("Désinstaller", f"Lancer le désinstallateur pour {name} ?"):
                subprocess.Popen(self.apps_data[name], shell=True)

    def get_hash(self, path):
        try:
            with open(path, 'rb') as f: return hashlib.md5(f.read(65536)).hexdigest()
        except: return None

    def run_preview(self):
        if not self.selected_folder and not self.vars["temp"].get():
            messagebox.showwarning("Cible", "Sélectionnez un dossier ou cochez 'Système'.")
            return
        self.progress.set(0.3)
        self.update()
        found, exts, hashes = [], [], {}
        if self.vars["docs"].get(): exts += ['.xml', '.doc', '.docx', '.pdf', '.txt']
        if self.vars["music"].get(): exts += ['.mp3', '.wav']
        if self.vars["video"].get(): exts += ['.mp4', '.mov', '.mkv']
        exclusions = [x.strip().lower() for x in self.exclude_entry.get().split(",") if x.strip()]
        if self.selected_folder:
            for root, _, files in os.walk(self.selected_folder):
                for f in files:
                    if any(p in f.lower() for p in exclusions): continue
                    path = os.path.join(root, f)
                    if any(f.lower().endswith(e) for e in exts): found.append(path)
                    if self.vars["dupes"].get():
                        h = self.get_hash(path)
                        if h:
                            if h in hashes: found.append(path)
                            else: hashes[h] = path
        self.files_to_delete = list(set(found))
        self.progress.set(1)
        if self.preview_win and self.preview_win.winfo_exists(): self.preview_win.destroy()
        self.preview_win = ctk.CTkToplevel(self)
        self.preview_win.geometry("750x550")
        self.preview_win.attributes("-topmost", True)
        ctk.CTkLabel(self.preview_win, text=f"{len(self.files_to_delete)} fichiers trouvés", font=("Segoe UI", 14, "bold")).pack(pady=10)
        txt = ctk.CTkTextbox(self.preview_win, width=700, height=420)
        txt.pack(padx=15, pady=10)
        for f in self.files_to_delete: txt.insert("end", f + "\n")

    def start_cleaning(self):
        if not self.files_to_delete and not self.vars["temp"].get(): return
        if not messagebox.askyesno("Confirmation", f"Voulez-vous supprimer ces {len(self.files_to_delete)} fichiers ?"): return
        log, count = f"RAPPORT DU {datetime.now()}\n", 0
        for p in self.files_to_delete:
            try:
                os.unlink(p)
                log += f"[OK] {p}\n"
                count += 1
            except: log += f"[FAIL] {p}\n"
        if self.vars["temp"].get():
            try: winshell.recycle_bin().empty(confirm=False, show_progress=False)
            except: pass
        report_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'Rapport_Nettoyage_Pro.txt')
        with open(report_path, "w", encoding="utf-8") as f: f.write(log)
        messagebox.showinfo("Fait", f"{count} fichiers traités. Rapport sur votre bureau.")

if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()