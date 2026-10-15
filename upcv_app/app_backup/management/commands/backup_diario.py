import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Genera backup diario (DB + media), comprime ZIP y elimina backups antiguos"

    def handle(self, *args, **kwargs):
        fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_dir = os.path.join(settings.BASE_DIR, "backups")

        # Crear carpeta backups/
        os.makedirs(backup_dir, exist_ok=True)

        # ======================
        # 📌 1. Rutas importantes
        # ======================
        db = settings.DATABASES["default"]
        db_name = db["NAME"]
        db_user = db["USER"]
        db_pass = db["PASSWORD"]
        db_host = db["HOST"]
        db_port = db["PORT"]

        backup_sql = os.path.join(backup_dir, f"backup_{fecha}.sql")
        media_src = settings.MEDIA_ROOT
        media_temp = os.path.join(backup_dir, f"media_{fecha}")

        # 🔥 Ruta completa al pg_dump (Windows)
        pg_dump_path = r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"

        # ======================
        # 📌 2. Backup SQL
        # ======================
        self.stdout.write("📦 Creando backup de la base de datos...")

        os.environ["PGPASSWORD"] = db_pass
        comando_pg = [
            pg_dump_path,
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-F", "p",
            "-f", backup_sql,
            db_name,
        ]

        try:
            subprocess.run(comando_pg, check=True)
            self.stdout.write(self.style.SUCCESS(f"✔ Backup DB generado: {backup_sql}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error backup DB: {e}"))

        # ======================
        # 📌 3. Copia carpeta media
        # ======================
        self.stdout.write("📁 Copiando carpeta MEDIA...")

        try:
            shutil.copytree(media_src, media_temp)
            self.stdout.write(self.style.SUCCESS("✔ Carpeta media copiada"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error copiando media: {e}"))

        # ======================
        # 📌 4. COMPRIMIR TODO A ZIP
        # ======================
        zip_path = os.path.join(backup_dir, f"backup_{fecha}.zip")

        self.stdout.write("🗜 Comprimendo backup en ZIP...")

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Agregar archivo SQL
                if os.path.exists(backup_sql):
                    zipf.write(backup_sql, os.path.basename(backup_sql))

                # Agregar carpeta media
                for root, dirs, files in os.walk(media_temp):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, media_temp)
                        zipf.write(file_path, f"media/{arcname}")

            self.stdout.write(self.style.SUCCESS(f"✔ ZIP creado: {zip_path}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error comprimiendo ZIP: {e}"))

        # ======================
        # 📌 5. BORRAR ARCHIVOS TEMPORALES
        # ======================
        if os.path.exists(backup_sql):
            os.remove(backup_sql)

        if os.path.exists(media_temp):
            shutil.rmtree(media_temp)

        # ======================
        # 📌 6. BORRAR BACKUPS > 30 DÍAS
        # ======================
        self.stdout.write("🧹 Eliminando backups mayores de 30 días...")

        limite = datetime.now() - timedelta(days=30)

        try:
            for archivo in os.listdir(backup_dir):
                ruta = os.path.join(backup_dir, archivo)
                if os.path.isfile(ruta):
                    fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta))
                    if fecha_mod < limite:
                        os.remove(ruta)
                        self.stdout.write(f"🗑 Eliminado: {archivo}")

            self.stdout.write(self.style.SUCCESS("✔ Limpieza de backups antigua completada"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error limpiando backups: {e}"))

        self.stdout.write(self.style.SUCCESS("🎉 Backup diario COMPLETO"))
