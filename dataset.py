import pandas as pd
import numpy as np
import random

# Function to generate random data for the dataset
def generate_data(start_date, end_date, countries, cities, shops):
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    data = []

    for date in dates:
        country = random.choice(countries)
        city = random.choice(cities[country])
        shop = random.choice(shops[city])
        target = random.randint(10, 500)  # Random sales numbers
        data.append([date.strftime('%Y-%m-%d'), country, city, shop, target])

    df = pd.DataFrame(data, columns=['Date', 'Country', 'City', 'Shop', 'Target'])
    df['Target'] = pd.to_numeric(df['Target'], errors='coerce')  # Ensure Target is numeric
    return df

# Define categorical values
countries = ['USA', 'Canada', 'UK']
cities = {
    'USA': ['New York', 'Los Angeles', 'Chicago'],
    'Canada': ['Toronto', 'Vancouver', 'Montreal'],
    'UK': ['London', 'Manchester', 'Edinburgh']
}
shops = {
    'New York': ['Shop A', 'Shop B'],
    'Los Angeles': ['Shop C', 'Shop D'],
    'Chicago': ['Shop E'],
    'Toronto': ['Shop F', 'Shop G'],
    'Vancouver': ['Shop H'],
    'Montreal': ['Shop I'],
    'London': ['Shop J', 'Shop K'],
    'Manchester': ['Shop L'],
    'Edinburgh': ['Shop M']
}

# Generate train and test datasets
train_data = generate_data('2020-01-01', '2023-12-31', countries, cities, shops)
test_data = generate_data('2024-01-01', '2024-12-31', countries, cities, shops)

# Save to Excel
train_data.to_excel('train_data.xlsx', index=False)
test_data.to_excel('test_data.xlsx', index=False)
