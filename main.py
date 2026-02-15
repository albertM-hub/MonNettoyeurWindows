import customtkinter as ctk
import winshell
import os
import shutil
import hashlib
import psutil
import platform
import winreg
import subprocess
import requests
import json
import zipfile
import io
import sys
import tempfile
from tkinter import filedialog, messagebox
from datetime import datetime
from pathlib import Path
import send2trash  # Note: c'est bien "send2trash" avec 'h'
import logging
from logging.handlers import RotatingFileHandler

# Configuration du logging sécurisé
log_dir = Path.home() / "AppData" / "Local" / "CleanerPro" / "Logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "cleaner_pro.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(log_file, maxBytes=1048576, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark") 
ctk.set_default_color_theme("green") 

class UpdateManager:
    """Gestionnaire de mises à jour automatique"""
    
    # À MODIFIER : Mettez votre propre dépôt GitHub ici
    GITHUB_API = "https://api.github.com/repos/votreusername/cleaner-pro/releases/latest"
    CURRENT_VERSION = "1.2"
    
    @classmethod
    def check_for_updates(cls, parent=None):
        """Vérifie les mises à jour sur GitHub"""
        try:
            response = requests.get(cls.GITHUB_API, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data['tag_name'].lstrip('v')
                
                if cls._compare_versions(latest_version, cls.CURRENT_VERSION) > 0:
                    return {
                        'available': True,
                        'version': latest_version,
                        'url': data['html_url'],
                        'download_url': data['assets'][0]['browser_download_url'] if data['assets'] else None,
                        'changelog': data['body']
                    }
            return {'available': False}
        except Exception as e:
            logger.error(f"Erreur vérification mise à jour: {e}")
            return {'available': False, 'error': str(e)}
    
    @classmethod
    def _compare_versions(cls, v1, v2):
        """Compare deux versions"""
        v1_parts = [int(x) for x in v1.split('.')]
        v2_parts = [int(x) for x in v2.split('.')]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1_part = v1_parts[i] if i < len(v1_parts) else 0
            v2_part = v2_parts[i] if i < len(v2_parts) else 0
            if v1_part != v2_part:
                return v1_part - v2_part
        return 0
    
    @classmethod
    def perform_update(cls, download_url, parent=None):
        """Télécharge et installe la mise à jour"""
        try:
            # Créer un dossier temporaire
            temp_dir = Path(tempfile.mkdtemp())
            download_path = temp_dir / "update.zip"
            
            # Télécharger la mise à jour
            response = requests.get(download_url, stream=True)
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Extraire
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Créer un script de mise à jour
            update_script = temp_dir / "update.bat"
            current_exe = sys.executable if getattr(sys, 'frozen', False) else __file__
            
            script_content = f"""@echo off
timeout /t 2 /nobreak >nul
copy /y "{temp_dir}\\*" "{Path(current_exe).parent}"
start "" "{current_exe}"
del "%~f0"
"""
            with open(update_script, 'w') as f:
                f.write(script_content)
            
            # Lancer le script de mise à jour et fermer l'application
            subprocess.Popen([str(update_script)], shell=True)
            if parent:
                parent.quit()
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour: {e}")
            return False

class SecureFileManager:
    """Gestionnaire de fichiers sécurisé"""
    
    # Extensions système à protéger
    SYSTEM_EXTENSIONS = {'.exe', '.dll', '.sys', '.drv', '.ocx', '.scr', '.bat', '.cmd', '.vbs', '.ps1'}
    
    # Dossiers critiques à ne jamais scanner
    CRITICAL_PATHS = [
        Path('C:/Windows'),
        Path('C:/Program Files'),
        Path('C:/Program Files (x86)'),
        Path('C:/System32'),
        Path.home() / 'AppData'
    ]
    
    @classmethod
    def is_safe_to_delete(cls, filepath):
        """Vérifie si un fichier peut être supprimé en toute sécurité"""
        path = Path(filepath)
        
        # Vérifier les extensions système
        if path.suffix.lower() in cls.SYSTEM_EXTENSIONS:
            return False, "Extension système protégée"
        
        # Vérifier les dossiers critiques
        for critical in cls.CRITICAL_PATHS:
            try:
                if str(path).lower().startswith(str(critical).lower()):
                    return False, "Dossier système protégé"
            except:
                continue
        
        # Vérifier les permissions
        if not os.access(path, os.W_OK):
            return False, "Permission insuffisante"
        
        return True, "OK"
    
    @classmethod
    def move_to_trash(cls, filepath):
        """Déplace vers la corbeille au lieu de supprimer définitivement"""
        try:
            send2trash.send2trash(str(filepath))
            return True, "Déplacé vers la corbeille"
        except Exception as e:
            return False, str(e)

class CleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Mon Compagnon de Nettoyage Pro - V{UpdateManager.CURRENT_VERSION}")
        self.geometry("950x1000")  # Légèrement plus grand pour tout afficher
        
        self.selected_folder = ""
        self.tools_folder = ""
        self.files_to_delete = []
        self.apps_data = {}
        self.preview_win = None
        self.backup_folder = None
        
        # Vérifier les mises à jour au démarrage (désactivé par défaut pour éviter les erreurs)
        # self.after(1000, self.check_updates_startup)
        
        # --- SYSTÈME D'ONGLETS ---
        self.tabview = ctk.CTkTabview(self, width=900, height=900, fg_color="#2B2B2B")
        self.tabview.pack(pady=10, padx=20)
        
        self.tab_clean = self.tabview.add("Nettoyage")
        self.tab_tools = self.tabview.add("Outils & Système")
        self.tab_apps = self.tabview.add("Programmes")
        self.tab_help = self.tabview.add("Mode d'emploi")
        self.tab_updates = self.tabview.add("Mises à jour")

        self.setup_clean_tab()
        self.setup_tools_tab()
        self.setup_apps_tab()
        self.setup_help_tab()
        self.setup_updates_tab()

    def check_updates_startup(self):
        """Vérifie les mises à jour au démarrage"""
        update_info = UpdateManager.check_for_updates(self)
        if update_info.get('available'):
            if messagebox.askyesno(
                "Mise à jour disponible",
                f"Une nouvelle version {update_info['version']} est disponible !\n\n"
                f"Nouveautés:\n{update_info['changelog']}\n\n"
                "Voulez-vous mettre à jour maintenant ?"
            ):
                self.perform_update(update_info)

    def perform_update(self, update_info):
        """Effectue la mise à jour"""
        if update_info.get('download_url'):
            success = UpdateManager.perform_update(update_info['download_url'], self)
            if success:
                messagebox.showinfo("Mise à jour", "Mise à jour en cours... L'application va redémarrer.")
            else:
                messagebox.showerror("Erreur", "Échec de la mise à jour. Veuillez réessayer plus tard.")

    def setup_updates_tab(self):
        """Configure l'onglet des mises à jour"""
        # En-tête
        ctk.CTkLabel(
            self.tab_updates, 
            text="🔄 Gestionnaire de Mises à Jour", 
            font=("Segoe UI", 26, "bold"), 
            text_color="#FFCC70"
        ).pack(pady=15)
        
        # Frame principal
        main_frame = ctk.CTkFrame(self.tab_updates, fg_color="#333333", corner_radius=15)
        main_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Version actuelle
        version_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        version_frame.pack(pady=20)
        
        ctk.CTkLabel(
            version_frame,
            text="Version actuelle:",
            font=("Segoe UI", 14)
        ).pack(side="left", padx=5)
        
        self.current_version_label = ctk.CTkLabel(
            version_frame,
            text=f"v{UpdateManager.CURRENT_VERSION}",
            font=("Segoe UI", 16, "bold"),
            text_color="#2ECC71"
        )
        self.current_version_label.pack(side="left", padx=5)
        
        # Bouton de vérification
        ctk.CTkButton(
            main_frame,
            text="🔍 Vérifier les mises à jour",
            fg_color="#E67E22",
            hover_color="#D35400",
            height=40,
            command=self.check_updates_manual
        ).pack(pady=20)
        
        # Informations sur la configuration
        info_text = ctk.CTkLabel(
            main_frame,
            text="Pour activer les mises à jour automatiques, modifiez\n"
                 "l'URL GitHub dans le code source (ligne 38).",
            font=("Segoe UI", 12),
            text_color="#AAAAAA"
        )
        info_text.pack(pady=10)
        
        # Zone d'information
        self.update_info_frame = ctk.CTkFrame(main_frame, fg_color="#1E1E1E", corner_radius=10)
        self.update_info_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.update_info_text = ctk.CTkTextbox(
            self.update_info_frame,
            width=750,
            height=250,
            fg_color="#1E1E1E",
            font=("Consolas", 12)
        )
        self.update_info_text.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Message par défaut
        self.update_info_text.insert("end", "Cliquez sur 'Vérifier les mises à jour' pour commencer.\n\n")
        self.update_info_text.insert("end", "Note: La vérification automatique au démarrage est désactivée par défaut.")

    def check_updates_manual(self):
        """Vérification manuelle des mises à jour"""
        self.update_info_text.delete("0.0", "end")
        self.update_info_text.insert("end", "🔍 Vérification des mises à jour en cours...\n\n")
        self.update()
        
        update_info = UpdateManager.check_for_updates(self)
        
        if update_info.get('error'):
            self.update_info_text.insert("end", f"❌ Erreur: {update_info['error']}\n\n")
            self.update_info_text.insert("end", "Cela peut être dû à :\n")
            self.update_info_text.insert("end", "• Pas de connexion internet\n")
            self.update_info_text.insert("end", "• L'URL GitHub n'est pas configurée\n")
            self.update_info_text.insert("end", "• Le dépôt n'existe pas\n\n")
            self.update_info_text.insert("end", "Pour tester, vous pouvez utiliser cette URL de démo :\n")
            self.update_info_text.insert("end", "https://api.github.com/repos/octocat/Hello-World/releases/latest")
        
        elif update_info.get('available'):
            self.update_info_text.insert("end", f"✅ Mise à jour disponible!\n\n")
            self.update_info_text.insert("end", f"Version: {update_info['version']}\n")
            self.update_info_text.insert("end", f"URL: {update_info['url']}\n\n")
            self.update_info_text.insert("end", f"Changements:\n{update_info['changelog']}\n")
            
            if messagebox.askyesno(
                "Mise à jour disponible",
                f"Version {update_info['version']} disponible.\nVoulez-vous mettre à jour maintenant ?"
            ):
                self.perform_update(update_info)
        else:
            self.update_info_text.insert("end", "✅ Vous avez la dernière version !\n")
            messagebox.showinfo("Mises à jour", "Vous avez la dernière version de l'application.")

    def setup_clean_tab(self):
        ctk.CTkLabel(
            self.tab_clean, 
            text="🛡️ Maintenance des Fichiers", 
            font=("Segoe UI", 26, "bold"), 
            text_color="#FFCC70"
        ).pack(pady=15)
        
        # Frame principal avec options de sécurité
        f_frame = ctk.CTkFrame(self.tab_clean, fg_color="#333333", corner_radius=15)
        f_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkButton(
            f_frame, 
            text="📁 1. CHOISIR LE DOSSIER CIBLE", 
            fg_color="#D35400", 
            hover_color="#E67E22", 
            command=self.browse_folder
        ).pack(pady=15)
        
        self.path_label = ctk.CTkLabel(
            f_frame, 
            text="Aucune cible sélectionnée", 
            font=("Segoe UI", 12, "italic")
        )
        self.path_label.pack(pady=5)

        # Zone d'exclusion améliorée
        exclude_frame = ctk.CTkFrame(self.tab_clean, fg_color="transparent")
        exclude_frame.pack(pady=10, fill="x")
        
        ctk.CTkLabel(
            exclude_frame,
            text="🔒 Protection:",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", padx=20)
        
        self.exclude_entry = ctk.CTkEntry(
            exclude_frame, 
            placeholder_text="Mots-clés à protéger (séparés par des virgules)...", 
            width=650, 
            height=40
        )
        self.exclude_entry.pack(pady=5, padx=20)
        
        ctk.CTkLabel(
            exclude_frame,
            text="Exemple: important, travail, photos vacances",
            font=("Segoe UI", 10),
            text_color="#888888"
        ).pack(anchor="w", padx=20)

        # Options de nettoyage
        opt_frame = ctk.CTkFrame(self.tab_clean, fg_color="transparent")
        opt_frame.pack(pady=10, fill="both")
        
        self.vars = {
            "temp": ctk.BooleanVar(value=True),
            "docs": ctk.BooleanVar(value=False),
            "music": ctk.BooleanVar(value=False),
            "video": ctk.BooleanVar(value=False),
            "dupes": ctk.BooleanVar(value=False),
            "backup": ctk.BooleanVar(value=True)
        }
        
        self.add_check(opt_frame, "🗑️ Nettoyer Corbeille et Fichiers Temporaires", "temp")
        self.add_check(opt_frame, "📄 Scanner et Supprimer Docs / XML", "docs")
        self.add_check(opt_frame, "🎵 Scanner et Supprimer Musiques", "music")
        self.add_check(opt_frame, "🎬 Scanner et Supprimer Vidéos", "video")
        self.add_check(opt_frame, "👥 Rechercher les DOUBLONS (MD5)", "dupes")
        self.add_check(opt_frame, "💾 Sauvegarder avant suppression", "backup", "#27AE60")

        # Barre de progression
        self.progress = ctk.CTkProgressBar(self.tab_clean, width=700, progress_color="#FFCC70")
        self.progress.set(0)
        self.progress.pack(pady=25)

        # Boutons d'action
        btn_frame = ctk.CTkFrame(self.tab_clean, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="🔍 2. ANALYSER L'ESPACE", 
            fg_color="#5D6D7E", 
            width=200, 
            height=45, 
            command=self.run_preview
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="🚀 3. LANCER LE NETTOYAGE", 
            fg_color="#E67E22", 
            height=55, 
            font=("Segoe UI", 16, "bold"), 
            command=self.start_cleaning
        ).pack(side="left", padx=10)
        
        # Statut
        self.status_label = ctk.CTkLabel(
            self.tab_clean, 
            text="Prêt", 
            text_color="#AAAAAA"
        )
        self.status_label.pack()

    def add_check(self, master, text, var, color="#E67E22"):
        """Ajoute une checkbox avec style"""
        ctk.CTkCheckBox(
            master, 
            text=text, 
            variable=self.vars[var], 
            font=("Segoe UI", 13), 
            checkmark_color="#FFCC70", 
            fg_color=color
        ).pack(pady=6, padx=80, anchor="w")

    def setup_tools_tab(self):
        # Diagnostic Système
        ctk.CTkLabel(
            self.tab_tools, 
            text="📊 Diagnostic Système", 
            font=("Segoe UI", 24, "bold"), 
            text_color="#FFCC70"
        ).pack(pady=15)
        
        self.diag_frame = ctk.CTkFrame(self.tab_tools, fg_color="#1E1E1E", corner_radius=15)
        self.diag_frame.pack(pady=10, padx=20, fill="x")
        
        self.info_label = ctk.CTkLabel(
            self.diag_frame, 
            text="Cliquez sur 'Actualiser' pour voir les détails", 
            font=("Consolas", 12), 
            justify="left"
        )
        self.info_label.pack(pady=20, padx=20)
        
        # Boutons d'action système
        sys_btn_frame = ctk.CTkFrame(self.tab_tools, fg_color="transparent")
        sys_btn_frame.pack(pady=5)
        
        ctk.CTkButton(
            sys_btn_frame, 
            text="🔄 ACTUALISER LES INFOS PC", 
            fg_color="#273746", 
            command=self.show_system_info
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            sys_btn_frame, 
            text="🧹 NETTOYER LE DISQUE", 
            fg_color="#C0392B", 
            command=self.run_disk_cleanup
        ).pack(side="left", padx=5)

        # Top 20 Fichiers Lourds
        ctk.CTkLabel(
            self.tab_tools, 
            text="📂 Analyse des Gros Fichiers", 
            font=("Segoe UI", 24, "bold"), 
            text_color="#FFCC70"
        ).pack(pady=(30, 5))
        
        tools_btn_frame = ctk.CTkFrame(self.tab_tools, fg_color="transparent")
        tools_btn_frame.pack(pady=10)
        
        ctk.CTkButton(
            tools_btn_frame, 
            text="📁 Choisir Dossier/Disque", 
            fg_color="#2980B9", 
            command=self.browse_tools_folder
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            tools_btn_frame, 
            text="🔎 Scanner", 
            fg_color="#E67E22", 
            command=self.find_large_files
        ).pack(side="left", padx=10)

        self.tools_path_label = ctk.CTkLabel(
            self.tab_tools, 
            text="Aucun dossier sélectionné", 
            font=("Segoe UI", 11, "italic")
        )
        self.tools_path_label.pack()

        # Zone de texte avec barre de défilement
        self.large_files_box = ctk.CTkTextbox(
            self.tab_tools, 
            width=800, 
            height=250, 
            fg_color="#1E1E1E", 
            font=("Consolas", 12)
        )
        self.large_files_box.pack(pady=10, padx=20)

    def setup_apps_tab(self):
        ctk.CTkLabel(
            self.tab_apps, 
            text="📦 Gestion des Logiciels", 
            font=("Segoe UI", 22, "bold"), 
            text_color="#FFCC70"
        ).pack(pady=15)
        
        uninst_frame = ctk.CTkFrame(self.tab_apps, fg_color="#333333")
        uninst_frame.pack(pady=10, padx=20, fill="x")
        
        self.app_to_remove = ctk.CTkEntry(
            uninst_frame, 
            placeholder_text="Copiez le nom exact du programme ici...", 
            width=450
        )
        self.app_to_remove.pack(side="left", padx=10, pady=15)
        
        ctk.CTkButton(
            uninst_frame, 
            text="DÉSINSTALLER", 
            fg_color="#E74C3C", 
            command=self.uninstall_app
        ).pack(side="left", padx=10)
        
        self.app_listbox = ctk.CTkTextbox(self.tab_apps, width=750, height=430)
        self.app_listbox.pack(pady=10, padx=20)
        
        ctk.CTkButton(
            self.tab_apps, 
            text="🔄 Actualiser la liste", 
            command=self.list_installed_apps
        ).pack(pady=10)

    def setup_help_tab(self):
        scroll_help = ctk.CTkScrollableFrame(self.tab_help, width=800, height=800, fg_color="transparent")
        scroll_help.pack(pady=10, padx=10, fill="both", expand=True)

        sections = [
            ("🛡️ SÉCURITÉ AVANT TOUT", "L'analyse (Étape 2) est obligatoire. Elle vous montre la liste des fichiers avant d'effacer quoi que ce soit. Rien n'est supprimé sans votre clic final sur 'Lancer le nettoyage'."),
            ("👥 LES DOUBLONS", "Le programme compare le contenu réel des fichiers (MD5). L'original est TOUJOURS conservé, seules les copies sont listées pour suppression."),
            ("📂 OUTILS DE DIAGNOSTIC", "L'onglet Outils vous permet de voir l'état de votre RAM et de votre processeur, ainsi que de débusquer les fichiers qui saturent votre disque."),
            ("📦 GESTION DES APPS", "Pour désinstaller un programme, copiez son nom dans la barre rouge. Cela lance la procédure officielle de Windows pour un retrait propre."),
            ("📝 RAPPORTS", "Après chaque nettoyage, un fichier de rapport est créé sur votre bureau avec la date et l'heure pour garder une trace de chaque action."),
            ("🔄 MISES À JOUR", "L'onglet 'Mises à jour' peut vérifier les nouvelles versions. Pour l'activer, configurez votre dépôt GitHub dans le code.")
        ]

        for title, content in sections:
            lbl_title = ctk.CTkLabel(
                scroll_help, 
                text=title, 
                font=("Segoe UI", 18, "bold"), 
                text_color="#E67E22"
            )
            lbl_title.pack(pady=(15, 5), padx=20, anchor="w")
            
            lbl_content = ctk.CTkLabel(
                scroll_help, 
                text=content, 
                font=("Segoe UI", 13), 
                wraplength=750, 
                justify="left"
            )
            lbl_content.pack(pady=(0, 10), padx=30, anchor="w")
            
            ctk.CTkFrame(scroll_help, height=2, fg_color="#444444").pack(fill="x", padx=20)

    def show_system_info(self):
        try:
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
        except Exception as e:
            self.info_label.configure(text=f"Erreur lors de la récupération des infos: {e}", text_color="#FF4444")

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
        try:
            for root, _, files in os.walk(target):
                for f in files:
                    p = os.path.join(root, f)
                    try: 
                        file_list.append((p, os.path.getsize(p)))
                    except: 
                        continue
            
            file_list.sort(key=lambda x: x[1], reverse=True)
            self.large_files_box.delete("0.0", "end")
            
            for i, (p, s) in enumerate(file_list[:20]):
                size_str = self.format_size(s)
                line = f"[{size_str}] -> {os.path.basename(p)}\n"
                
                if i == 0:
                    self.large_files_box.insert("end", "🔥 LE PLUS GROS : " + line)
                else:
                    self.large_files_box.insert("end", f"{i+1}. {line}")
        except Exception as e:
            self.large_files_box.insert("end", f"Erreur lors du scan: {e}")

    def browse_folder(self):
        """Sélectionne un dossier avec vérification de sécurité"""
        folder = filedialog.askdirectory()
        if folder:
            # Vérifier que ce n'est pas un dossier critique
            path = Path(folder)
            for critical in SecureFileManager.CRITICAL_PATHS:
                try:
                    if str(path).lower().startswith(str(critical).lower()):
                        if not messagebox.askyesno(
                            "Attention", 
                            f"Ce dossier semble être un dossier système ({critical.name}).\n"
                            "La suppression de fichiers système peut endommager Windows.\n\n"
                            "Voulez-vous vraiment continuer ?"
                        ):
                            return
                except:
                    continue
            
            self.selected_folder = folder
            self.path_label.configure(text=f"Cible : {folder}", text_color="#FFCC70")
            logger.info(f"Dossier sélectionné: {folder}")

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
                                try: 
                                    cmd = winreg.QueryValueEx(sk, "UninstallString")[0]
                                except: 
                                    cmd = ""
                                self.apps_data[name.lower()] = cmd
                                self.app_listbox.insert("end", f"• {name}\n")
                        except: 
                            continue
            except: 
                continue
        
        if not self.apps_data:
            self.app_listbox.insert("end", "Aucune application trouvée ou accès refusé.")

    def uninstall_app(self):
        """Désinstallation sécurisée des applications"""
        name = self.app_to_remove.get().lower().strip()
        if name in self.apps_data and self.apps_data[name]:
            cmd = self.apps_data[name]
            
            # Nettoyer la commande pour éviter les injections
            if cmd.startswith('"') and cmd.endswith('"'):
                cmd = cmd[1:-1]
            
            if messagebox.askyesno(
                "Désinstaller", 
                f"Lancer le désinstallateur pour {name} ?\n\n"
                "Commande: " + cmd
            ):
                try:
                    subprocess.Popen(cmd, shell=True)
                    logger.info(f"Désinstallation lancée pour: {name}")
                except Exception as e:
                    logger.error(f"Erreur désinstallation {name}: {e}")
                    messagebox.showerror("Erreur", f"Impossible de lancer la désinstallation:\n{e}")
        else:
            messagebox.showwarning("Non trouvé", f"Programme '{name}' non trouvé dans la liste.\nUtilisez le nom exact affiché dans la liste.")

    def get_hash(self, path):
        """Calcule le MD5 d'un fichier avec gestion d'erreur"""
        try:
            hash_md5 = hashlib.md5()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Erreur calcul hash {path}: {e}")
            return None

    def run_preview(self):
        """Analyse améliorée avec vérification MIME"""
        if not self.selected_folder and not self.vars["temp"].get():
            messagebox.showwarning("Cible", "Sélectionnez un dossier ou cochez 'Système'.")
            return
        
        self.status_label.configure(text="Analyse en cours...", text_color="#FFCC70")
        self.progress.set(0.3)
        self.update()
        
        found, exts, hashes = [], [], {}
        if self.vars["docs"].get(): 
            exts += ['.xml', '.doc', '.docx', '.pdf', '.txt', '.xls', '.xlsx', '.ppt', '.pptx']
        if self.vars["music"].get(): 
            exts += ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']
        if self.vars["video"].get(): 
            exts += ['.mp4', '.mov', '.mkv', '.avi', '.wmv', '.flv', '.webm']
        
        exclusions = [x.strip().lower() for x in self.exclude_entry.get().split(",") if x.strip()]
        
        if self.selected_folder:
            try:
                for root, _, files in os.walk(self.selected_folder):
                    for f in files:
                        # Vérifier les exclusions par mot-clé
                        if any(p in f.lower() for p in exclusions):
                            continue
                        
                        path = os.path.join(root, f)
                        
                        # Vérification de sécurité
                        is_safe, reason = SecureFileManager.is_safe_to_delete(path)
                        if not is_safe:
                            logger.warning(f"Fichier protégé ignoré: {path} - {reason}")
                            continue
                        
                        # Vérification par extension
                        if any(f.lower().endswith(e) for e in exts):
                            found.append(path)
                        
                        # Recherche de doublons
                        if self.vars["dupes"].get():
                            h = self.get_hash(path)
                            if h:
                                if h in hashes:
                                    found.append(path)
                                else:
                                    hashes[h] = path
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de l'analyse:\n{e}")
                return
        
        self.files_to_delete = list(set(found))
        self.progress.set(1)
        
        # Afficher la préview
        self.show_preview()
        self.status_label.configure(
            text=f"Analyse terminée: {len(self.files_to_delete)} fichiers trouvés", 
            text_color="#2ECC71"
        )

    def show_preview(self):
        """Affiche la préview des fichiers à supprimer"""
        if self.preview_win and self.preview_win.winfo_exists():
            self.preview_win.destroy()
        
        self.preview_win = ctk.CTkToplevel(self)
        self.preview_win.geometry("800x600")
        self.preview_win.title("Aperçu avant suppression")
        self.preview_win.attributes("-topmost", True)
        
        # En-tête
        header_frame = ctk.CTkFrame(self.preview_win, fg_color="#333333")
        header_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            header_frame, 
            text=f"📋 {len(self.files_to_delete)} fichiers trouvés", 
            font=("Segoe UI", 16, "bold")
        ).pack(pady=10)
        
        if self.vars["backup"].get():
            ctk.CTkLabel(
                header_frame,
                text="✓ Mode sauvegarde activé",
                text_color="#27AE60",
                font=("Segoe UI", 12)
            ).pack()
        
        # Zone de texte avec barre de défilement
        text_frame = ctk.CTkFrame(self.preview_win)
        text_frame.pack(padx=15, pady=10, fill="both", expand=True)
        
        txt = ctk.CTkTextbox(text_frame, width=750, height=450, font=("Consolas", 11))
        txt.pack(side="left", fill="both", expand=True)
        
        scrollbar = ctk.CTkScrollbar(text_frame, command=txt.yview)
        scrollbar.pack(side="right", fill="y")
        txt.configure(yscrollcommand=scrollbar.set)
        
        # Afficher les fichiers avec leur taille
        total_size = 0
        for f in sorted(self.files_to_delete):
            try:
                size = os.path.getsize(f)
                total_size += size
                size_str = self.format_size(size)
                txt.insert("end", f"{size_str:>10} - {f}\n")
            except:
                txt.insert("end", f"     ?    - {f}\n")
        
        # Résumé
        summary_frame = ctk.CTkFrame(self.preview_win, fg_color="#333333")
        summary_frame.pack(fill="x", pady=10)
        
        total_size_str = self.format_size(total_size)
        ctk.CTkLabel(
            summary_frame,
            text=f"Espace total libérable: {total_size_str}",
            font=("Segoe UI", 14, "bold"),
            text_color="#FFCC70"
        ).pack(pady=10)

    def format_size(self, size):
        """Formate la taille en unités lisibles"""
        for unit in ['o', 'Ko', 'Mo', 'Go', 'To']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} Po"

    def start_cleaning(self):
        """Nettoyage sécurisé avec option de sauvegarde"""
        if not self.files_to_delete and not self.vars["temp"].get():
            messagebox.showinfo("Info", "Aucun fichier à nettoyer.")
            return
        
        if not messagebox.askyesno(
            "Confirmation", 
            f"Voulez-vous supprimer ces {len(self.files_to_delete)} fichiers ?\n\n"
            "⚠️ Cette action est irréversible si vous ne cochez pas l'option de sauvegarde."
        ):
            return
        
        self.status_label.configure(text="Nettoyage en cours...", text_color="#E67E22")
        self.progress.set(0)
        
        log = f"RAPPORT DE NETTOYAGE - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        log += "="*60 + "\n\n"
        
        count = 0
        total_size = 0
        
        # Créer dossier de sauvegarde si nécessaire
        backup_dir = None
        if self.vars["backup"].get() and self.files_to_delete:
            backup_dir = Path.home() / "Desktop" / f"CleanerPro_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            log += f"Dossier de sauvegarde: {backup_dir}\n\n"
        
        for i, p in enumerate(self.files_to_delete):
            self.progress.set((i + 1) / len(self.files_to_delete))
            self.update()
            
            try:
                # Sauvegarde si demandée
                if backup_dir:
                    path = Path(p)
                    dest = backup_dir / path.name
                    # Éviter les collisions de noms
                    counter = 1
                    while dest.exists():
                        dest = backup_dir / f"{path.stem}_{counter}{path.suffix}"
                        counter += 1
                    shutil.copy2(p, dest)
                    log += f"[SAUVEGARDE] {p} -> {dest}\n"
                
                # Déplacement vers corbeille (plus sûr que suppression définitive)
                success, msg = SecureFileManager.move_to_trash(p)
                if success:
                    log += f"[SUPPRIMÉ] {p}\n"
                    count += 1
                    try:
                        total_size += os.path.getsize(p)
                    except:
                        pass
                else:
                    log += f"[ERREUR] {p} - {msg}\n"
                    
            except Exception as e:
                log += f"[ERREUR] {p} - {str(e)}\n"
                logger.error(f"Erreur suppression {p}: {e}")
        
        # Nettoyer la corbeille si demandé
        if self.vars["temp"].get():
            try:
                winshell.recycle_bin().empty(confirm=False, show_progress=False)
                log += "\n[SYSTÈME] Corbeille vidée\n"
                logger.info("Corbeille vidée")
            except Exception as e:
                log += f"\n[ERREUR CORBEILLE] {e}\n"
                logger.error(f"Erreur vidage corbeille: {e}")
        
        # Générer le rapport
        report_path = Path.home() / "Desktop" / f"Rapport_Nettoyage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(log)
        
        # Résumé
        total_size_str = self.format_size(total_size)
        summary = f"{count} fichiers traités ({total_size_str} libérés)\nRapport sauvegardé sur le bureau"
        
        self.status_label.configure(text=summary, text_color="#2ECC71")
        self.progress.set(1)
        
        messagebox.showinfo(
            "Nettoyage terminé", 
            f"{summary}\n\nLe rapport détaillé a été enregistré."
        )
        
        logger.info(f"Nettoyage terminé: {count} fichiers, {total_size_str} libérés")
        
        # Réinitialiser la liste
        self.files_to_delete = []

    def run_disk_cleanup(self):
        """Lance l'outil de nettoyage de disque Windows"""
        try:
            subprocess.Popen(["cleanmgr.exe"])
            logger.info("Outil de nettoyage de disque lancé")
        except Exception as e:
            logger.error(f"Erreur lancement cleanmgr: {e}")
            messagebox.showerror("Erreur", "Impossible de lancer le nettoyage de disque")

if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()