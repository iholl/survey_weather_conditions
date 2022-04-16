import os, arcgis, requests
from numpy import append
import pandas as pd
from decouple import config
from zipfile import ZipFile

# # check if folder exists if not create one (params: path to check/create folder)
def check_create_folder(path):
    if not os.path.exists(path):
        os.mkdir(path)

# remove all the files in a folder except for the current data (param: path to folder to remove files from)
def clear_new_data(path):
    for clean_up in os.listdir(path):
        if not clean_up.endswith("current_data.csv"):    
            os.remove(os.path.join(path, clean_up))

# log into arcigs online account and export the required feature layer to a csv in the users arcgis online content
feature_layer_id = config("FEATURE_ID")
gis = arcgis.GIS(None, username=config("ARCGIS_ONLINE_USERNAME"), password=config("ARCGIS_ONLINE_PASSWORD"))
data = gis.content.get(feature_layer_id)
name = data.title.replace(" ", "_").lower()
csv = data.export(title=name, export_format="csv", parameters=None, wait=True)

# # check for the "data"
# #  directory if not create one, download the csv, and remove it
check_create_folder("data")
export_path = csv.download(save_path="data")
csv.delete()

# # check if there is a folder based on the feature title to store the data and create one if not
folder_path = "data/{}".format(name)
check_create_folder(folder_path)

# # extract the csv files from the downloaded zipfile and delete the zipped file
zipped_file = ZipFile(export_path)
zipped_file.extractall(folder_path)
zipped_file.close()
os.remove(export_path)

# set the new to the current current data, and clear out the other data
current_data = os.path.join(folder_path, "current_data.csv")
feature = "{}_{}.csv".format(config("LAYER_NAME"), config("LAYER_ID"))
new_data = os.path.join(folder_path, feature)

# if current data is not avaliable, create current data and remove files 
current_df = pd.read_csv(current_data)

df = current_df[["GlobalID","CreationDate", "x", "y"]]
df["Dates"] = pd.to_datetime(df["CreationDate"]).dt.date
df["Time"] = pd.to_datetime(df["CreationDate"]).dt.time
df["DateTime"] = pd.to_datetime(df["Dates"].astype(str) + " " + df["Time"].astype(str))
df["Unix"] = (df["DateTime"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")

weather_data = []

for idx, row in df.iterrows():
    try:
        url = "https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={}&lon={}&dt={}&appid={}"
        response = requests.get(url.format(row["y"],row["x"],row["Unix"],config("OPEN_WEATHER_API_KEY")))
        weather = response.json()
        print(idx, response)
        data_list = []

        data_list.append(row["GlobalID"])
        data_list.append(weather['current']['temp'] * 9/5 - 459.67)
        data_list.append(weather['current']['clouds'])
        data_list.append(weather['current']['wind_speed'])
        weather_data.append(data_list)
    except ValueError:
        print("The date provided is not within the past 5 days")

df = pd.DataFrame(weather_data, columns=["ParentGlobalID", "Temperature", "CloudCover", "WindSpeed"])
csv_name = "{}_weather_data.csv".format(name)
table = df.to_csv(os.path.join(folder_path, csv_name))

csv_item = gis.content.add(csv_name)
csv_item.move(config("ARCGIS_ONLINE_FOLDER_NAME"))
print("Weather data addd")