import os

def list_files(directory):
    """List all files in the given directory."""
    try:
        files = os.listdir(directory)
        return [f for f in files if os.path.isfile(os.path.join(directory, f))]
    except FileNotFoundError:
        return f"Error: The directory '{directory}' does not exist."
    except PermissionError:
        return f"Error: Permission denied to access '{directory}'."
    
if __name__ == "__main__":
    dir_path = input("Enter the directory path: ")
    files = list_files(dir_path)
    if isinstance(files, list):
        print("Files in directory:")
        for file in files:
            print(file)
    else:
        print(files)


#password=12345