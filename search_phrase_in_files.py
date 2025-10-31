import os

def list_files(directory):
    return [file for file in os.listdir(directory) if os.path.isfile(os.path.join(directory, file))]

def contains_phrase(file_path, phrase):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return any(phrase in line for line in f)
    

if __name__ == "__main__":
    search_phrase = input("Enter the search phrase: ")
    dir_path = input("Enter the directory path: ")
    
    files = list_files(dir_path)
    for file in files:
        file_path = os.path.join(dir_path, file)
        if contains_phrase(file_path, search_phrase):
            print(f"Found '{search_phrase}' in {file}")

    else:
        print("No files found containing the phrase.")