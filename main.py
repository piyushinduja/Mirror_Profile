from openai import OpenAI
from dotenv import load_dotenv
import os
from collections import defaultdict
import re
import json
import sys
import pandas as pd
from google import genai
import sys
from pathlib import Path
from google_docs_integration import create_google_doc

load_dotenv("../../.env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
client_name = "watson"

# TEMPERATURE = 0.25

def main():
    prompt_dir = "../prompts/"
    data_dir = "../data/"

    os.makedirs(rf"{data_dir}/{client_name}/", exist_ok=True)

    # Read the question answers
    question_answers_path = f"{data_dir}/{client_name}/question_answers.txt"
    question_answers = open(question_answers_path, "r", encoding="utf-8").read().strip()
    if len(question_answers) < 20:
        print("Question answers looks empty or too short."); sys.exit(1)

    # Generate the master_extraction using prompt 1
    print("Generating master extraction using prompt 1...")
    prompt1_path = f"{prompt_dir}/p1.txt"
    prompt1 = open(prompt1_path, "r", encoding="utf-8").read().strip()
    prompt1 = prompt1.replace("<<question_answers>>", question_answers)
    response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=prompt1,
    )
    master_extraction = response.text
    # master_extraction = "test"
    if master_extraction != "test" and len(master_extraction) < 20:
        print("Master extraction looks empty or too short."); sys.exit(1)
    with open(f"{data_dir}/{client_name}/master_extraction.txt", "w", encoding="utf-8") as f:
        f.write(master_extraction)

    common_includes = open(f"{prompt_dir}/common_includes.txt", "r", encoding="utf-8").read().strip()
    common_instructions = open(f"{prompt_dir}/common_instructions.txt", "r", encoding="utf-8").read().strip()

    final_mirror_profile = ""
    # generate section-wise mirror profile using prompts 2, 3, 4, ...
    for i in range(2, 16):
        print(f"Generating section {i-1} mirror profile using prompt {i}...")
        prompt_path = f"{prompt_dir}/p{i}.txt"
        prompt = open(prompt_path, "r", encoding="utf-8").read().strip()
        prompt = prompt.replace("<<master_extraction>>", master_extraction)
        prompt = prompt.replace("<<question_answers>>", question_answers)
        prompt = prompt.replace("<<common_includes>>", common_includes)
        prompt = prompt.replace("<<common_instructions>>", common_instructions)

        prompt = prompt.replace("<<section_number>>", str(i-1)) # Replace this at last because it is used in the "common instructions"
        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=prompt,
        )
        section_mirror_profile = response.text + "\n\n"
        # section_mirror_profile = "test"
        if section_mirror_profile != "test" and len(section_mirror_profile) < 20:
            print(f"Section {i-1} mirror profile looks empty or too short."); sys.exit(1)
        with open(f"{data_dir}/{client_name}/mirror_profile.txt", "a", encoding="utf-8") as f:
            f.write(section_mirror_profile)
        final_mirror_profile += section_mirror_profile
    
    doc_title = f"{client_name}_mirror_profile"
    response = create_google_doc(doc_title, final_mirror_profile)
    if response['success']:
        print(f"Successfully created Google Doc: {response['document_url']}")
    else:
        print(f"Failed to create Google Doc: {response['message']}")

if __name__ == "__main__":
    main()

