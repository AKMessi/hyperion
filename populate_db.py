import csv
from src.hyperion.database.operations import initialize_database, add_prospect

def populate_from_csv(csv_filepath='prospects.csv'):
    """Reads a CSV and populates the prospects table."""
    initialize_database()
    
    try:
        with open(csv_filepath, mode='r', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            prospects_to_add = []
            
            for row in csv_reader:
                first_name = row.get('First Name', '')
                last_name = row.get('Last Name', '')
                
                prospect = {
                    'id': f"prospect_{row.get('Email')}",
                    
                    'name': f"{first_name} {last_name}".strip(),
                    
                    'email': row.get('Email'),
                    'linkedin_url': row.get('Person Linkedin Url'),
                    'title': row.get('Title'),
                    'organization': {
                        'name': row.get('Company Name'),
                        'primary_domain': row.get('Website')
                    }
                }
                prospect['first_name'] = first_name
                prospect['last_name'] = last_name

                prospects_to_add.append(prospect)
            
            print(f"Found {len(prospects_to_add)} prospects in {csv_filepath}.")
            
            for p in prospects_to_add:
                add_prospect(p)
            
            print(f"Successfully added/updated {len(prospects_to_add)} prospects in the database.")

    except FileNotFoundError:
        print(f"Error: The file {csv_filepath} was not found. Please ensure it is in the root directory.")
    except KeyError as e:
        print(f"Error: A required column is missing from your CSV file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    populate_from_csv()