import os

with open("repo_structure.txt", "w") as f:
    for root, dirs, files in os.walk("."):
        level = root.replace(os.path.sep, "/").count("/")
        indent = " " * 4 * (level)
        f.write(f"{indent}{os.path.basename(root)}/\n")
        subindent = " " * 4 * (level + 1)
        for file in files:
            f.write(f"{subindent}{file}\n")