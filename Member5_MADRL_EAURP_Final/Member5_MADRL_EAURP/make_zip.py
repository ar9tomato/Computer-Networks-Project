import os
import zipfile

def package_project():
    zip_filename = 'Member5_MADRL_EAURP_Final.zip'
    
    print(f"Creating {zip_filename}...")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Exclude pycache and the zip itself
            if '__pycache__' in root or zip_filename in files:
                continue
            for file in files:
                if file == zip_filename:
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, '.')
                zipf.write(file_path, arcname)
                
    print(f"\nSuccessfully packaged into {zip_filename}")

if __name__ == "__main__":
    package_project()
