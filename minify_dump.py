import os
import re

input_path = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK\Saved\ALL_LOGIC_DUMP.txt"
output_path = r"C:\Users\USER\Documents\Unreal Projects\AOS_DK\Saved\CLEAN_LOGIC_DUMP_V2.txt"

if not os.path.exists(input_path):
    print(f"Помилка: Файл {input_path} не знайдено.")
    exit()

with open(input_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

clean_lines = []
for line in lines:
    stripped = line.strip()

    # 1. Ігноруємо координати, GUID, метадані
    ignore_starts = [
        "NodeGuid=", "GraphGuid=", "NodePosX=", "NodePosY=", "ExtraFlags=", 
        "bIsEditable=", "CategorySorting=", "MetaData=", "Schema=", "BlueprintSystemVersion="
    ]
    if any(stripped.startswith(x) for x in ignore_starts):
        continue
    if "SceneThumbnailInfo" in stripped or "EdGraphNode_Comment" in stripped:
        continue

    # 2. Обробка пінів ТА ЗБЕРЕЖЕННЯ ЗВ'ЯЗКІВ (LinkedTo)
    if stripped.startswith("CustomProperties Pin") or stripped.startswith("CustomProperties UserDefinedPin"):
        name_match = re.search(r'PinName="([^"]+)"', stripped)
        type_match = re.search(r'PinType\.PinCategory="([^"]+)"', stripped)
        dir_match = re.search(r'Direction="([^"]+)"', stripped)
        
        # Шукаємо, куди підключений дріт
        link_match = re.search(r'LinkedTo=\(([^)]+)\)', stripped)

        p_name = name_match.group(1) if name_match else "Unknown"
        p_type = type_match.group(1) if type_match else "exec"
        p_dir = dir_match.group(1).replace("EGPD_", "") if dir_match else "Input"
        
        pin_text = f"      [PIN] {p_dir}: {p_name} ({p_type})"
        
        # Якщо є підключення, додаємо його до рядка
        if link_match:
            raw_links = link_match.group(1).split(',')
            # Забираємо довгі цифрові ID, залишаємо лише назву цільової ноди
            clean_links = [l.strip().split(' ')[0] for l in raw_links if l.strip()]
            pin_text += f" ---> [Connected to: {', '.join(clean_links)}]"
            
        clean_lines.append(pin_text + "\n")
        continue

    # 3. Видаляємо довжелезні ExportPath="..." та PersistentGuid
    clean_line = re.sub(r'\s*ExportPath="[^"]+"', '', line)
    clean_line = re.sub(r'\s*PersistentGuid=[A-F0-9]+', '', clean_line)

    # Пропускаємо порожні рядки
    if clean_line.strip() == "" and stripped != "":
        continue

    clean_lines.append(clean_line)

with open(output_path, "w", encoding="utf-8") as f:
    f.writelines(clean_lines)

original_size = os.path.getsize(input_path) / 1024
new_size = os.path.getsize(output_path) / 1024

print(f"Готово! Зв'язки (дроти) відновлено.")
print(f"Оригінал: {original_size:.1f} KB")
print(f"Очищений: {new_size:.1f} KB")