import os
import random
import string

def generate_default_output_filename(input_file):
  """Generate default output filename from input filename

  Format: [basename]-transformed-[3random].csv
  Example: input.csv -> input-transformed-a3x.csv
  """
  # Get the base filename without extension
  base_name = os.path.splitext(os.path.basename(input_file))[0]

  # Generate 3 random alphanumeric characters
  random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))

  # Construct output filename
  output_filename = f"{base_name}-transformed-{random_chars}.csv"

  return output_filename
