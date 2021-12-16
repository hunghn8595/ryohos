import os

def get_unique_list(list_to_unique):
    unique_list = []
    for n in list_to_unique:
        if n not in unique_list:
            unique_list.append(n)
    return unique_list