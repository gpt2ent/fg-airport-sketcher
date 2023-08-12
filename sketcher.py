import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import numpy as np
import os
import re
import shutil
import tempfile
import subprocess

"""
Explanation of the pattern:

^ asserts the start of the line.

\s* matches any number of consecutive spaces or tab characters.

1 matches land airport code

\s+ matches one or more consecutive spaces or tab characters.

(?P<elevation>-?[\d.]+) captures the elevation as a named group, which can be any sequence of digits or periods.
The addition of -? before [\d.]+ allows for an optional dash - before the digits and periods, indicating a negative elevation value.

\s+ matches one or more consecutive spaces or tab characters.

[\d]+\s+[\d]+\s+ matches two groups of one or more digits followed by one or more consecutive spaces or tab characters.

(?P<icao>\S+) captures the ICAO code as a named group, which can be any sequence of non-whitespace characters.

\s+ matches one or more consecutive spaces or tab characters.

(?P<name>.+) captures the name as a named group, which can be any sequence of characters.

\s* matches any number of consecutive spaces or tab characters.

$ asserts the end of the line.
"""
REGEX_AIRPORT = r"^\s*1\s+(?P<elevation>-?[\d.]+)\s+[\d]+\s+[\d]+\s+(?P<icao>\S+)\s+(?P<name>.+)\s*$"



class Airport:
    def __init__(self, name, icao, elevation):
        self.name = name
        self.icao = icao
        self.elevation = elevation
        self.lats = []
        self.lons = []
        self.lat = None
        self.lon = None
        self.elevation_filename = None
        self.expected_folders = []

    def add_lat_lon(self, lat, lon):
        self.lats.append(lat)
        self.lons.append(lon)

    def process_lats_lons(self):
        if len(self.lats) == 0:
            return False
        self.lat = int(np.floor(np.mean(self.lats)))
        self.lon = int(np.floor(np.mean(self.lons)))

        lat_hemi = "N" if self.lat > 0 else "S"
        lon_hemi = "E" if self.lon > 0 else "W"

        self.elevation_filename = f"{lat_hemi}{abs(self.lat):02}{lon_hemi}{abs(self.lon):03}.hgt"
        # example: N02E003.hgt

        self.expected_folders = [f"{lon_hemi.lower()}{abs(int(np.floor(self.lon/10)*10)):03}{lat_hemi.lower()}{abs(int(np.floor(self.lat/10)*10)):02}",
                                 f"{lon_hemi.lower()}{abs(self.lon):03}{lat_hemi.lower()}{abs(self.lat):02}"]
        # example: e010n10/e011n17

        return True

    def is_ready(self):
        return self.lat is not None and self.lon is not None


class App(ttk.Frame):

    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("Airport Sketcher")
        self.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.does_docker_exist = False  # will be set to True if docker image is found
        self.airport = None
        self.create_widgets()

    def create_widgets(self):

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)
        self.rowconfigure(4, weight=1)
        self.rowconfigure(5, weight=1)
        self.rowconfigure(6, weight=1)

        # Airport .dat file
        self.dat_file_label = ttk.Label(self, text="Airport .dat file:")
        self.dat_file_label.grid(row=0, column=0, sticky=tk.W)

        self.dat_file_entry = ttk.Entry(self)
        self.dat_file_entry.grid(row=0, column=1, sticky=tk.W)

        self.dat_file_button = ttk.Button(self, text="Select .dat file", command=self.select_dat_file)
        self.dat_file_button.grid(row=0, column=2, sticky=tk.W)

        # Empty label to display loaded .dat file
        self.loaded_file_label = ttk.Label(self, text="")
        self.loaded_file_label.grid(row=1, column=0, sticky=tk.W)

        # Height (meters)
        self.height_label = ttk.Label(self, text="Elevation above sea level (meters):")
        self.height_label.grid(row=2, column=0, sticky=tk.W)

        vcmd = (self.register(self.validate_height), '%P')
        self.height_entry = ttk.Entry(self, validate='key', validatecommand=vcmd)
        self.height_entry.grid(row=2, column=1, sticky=tk.W)

        # Output scenery folder
        self.output_folder_label = ttk.Label(self, text="Output scenery folder:")
        self.output_folder_label.grid(row=3, column=0, sticky=tk.W)

        self.output_folder_entry = ttk.Entry(self)
        self.output_folder_entry.grid(row=3, column=1, sticky=tk.W)

        self.output_folder_button = ttk.Button(self, text="Select folder", command=self.select_output_folder)
        self.output_folder_button.grid(row=3, column=2, sticky=tk.W)

        # Process airport button
        self.process_button = ttk.Button(self, text="Process airport", command=self.process_airport)
        self.process_button.grid(row=4, column=0, columnspan=3)

        # Disabled textarea for log output
        self.log_textarea = tk.Text(self, state=tk.DISABLED, bg="white")
        self.log_textarea.grid(row=5, column=0, columnspan=3, sticky='nsew')
        self.log_textarea.bind("<1>", lambda event: self.log_textarea.focus_set())

        # Progressbar
        self.progressbar = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=200, mode='determinate')
        self.progressbar.grid(row=6, column=0, columnspan=3, sticky='nsew')

        self.write_log('Initialized')

        try:
            docker_check = subprocess.run(['docker', 'images', 'flightgear/terragear:ws20'], capture_output=True, text=True)
            if 'flightgear/terragear' in docker_check.stdout:
                self.write_log('Docker image found: flightgear/terragear:ws20')
                self.does_docker_exist = True
            else:
                self.write_log('Docker image not found. Downloading...')
                self.download_image()
        except subprocess.CalledProcessError as e:
            # Handle any error that occurred while running the Docker command
            self.write_log('Error occurred while checking Docker image')


    def select_dat_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("DAT Files", "*.dat")], master=self.master)
        self.dat_file_entry.delete(0, tk.END)
        self.dat_file_entry.insert(0, file_path)
        # self.loaded_file_label["text"] = "Loaded file: " + file_path
        self.parse_airport_data()

    def select_output_folder(self):
        folder_path = filedialog.askdirectory(master=self.master)
        self.output_folder_entry.delete(0, tk.END)
        self.output_folder_entry.insert(tk.END, folder_path)

    def log_validation_failed(self):
        self.write_log('='*50)
        self.write_log('VALIDATION FAILED! SEE ABOVE LOG FOR DETAILS')
        self.write_log('='*50)

    def process_airport(self):
        dat_file_path = self.dat_file_entry.get()
        output_folder_path = self.output_folder_entry.get()
        height = self.height_entry.get()

        self.write_log('='*50)
        self.write_log('VALIDATION')
        self.write_log('='*50)

        if not dat_file_path or not os.path.isfile(dat_file_path):
            self.write_log("Invalid DAT file path or file does not exist.")
            self.log_validation_failed()
            return

        if not self.airport.is_ready():
            self.write_log("Invalid airport data. See above log for details.")
            self.log_validation_failed()
            return

        if not output_folder_path:
            self.write_log("Output folder path is empty.")
            self.log_validation_failed()
            return

        try:
            int(height)
        except ValueError:
            self.write_log("Invalid height value.")
            self.log_validation_failed()
            return

        if not self.does_docker_exist:
            self.write_log("Cannot process airport without Docker.")
            self.log_validation_failed()
            return

        self.write_log('='*50)
        self.write_log("ALL CHECKS PASSED")
        self.write_log('='*50)

        self.progressbar.step(1)

        self.disable_all_buttons()

        # Step 1. In scenario folder, create folders /NavData/apt, copy dat file to /NavData/apt as {icao}.dat
        self.write_log('Moving airport to /NavData/apt')
        if not os.path.exists(os.path.join(output_folder_path, "NavData","apt")):
            os.makedirs(os.path.join(output_folder_path, "NavData","apt"))

        shutil.copy(dat_file_path, os.path.join(output_folder_path, "NavData","apt", f"{self.airport.icao}.dat"))
        self.progressbar.step(9)

        # Step 2. Create a temporary folder
        tgworkdir = tempfile.TemporaryDirectory()
        self.write_log(f'Created tempdir {tgworkdir.name}')
        self.progressbar.step(10)

        self.write_log('Copying files to tempdir')
        # Step 3. Copy the dat file to the temporary folder
        shutil.copy(dat_file_path, os.path.join(tgworkdir.name, f"{self.airport.icao}.dat"))
        self.progressbar.step(10)

        self.update()

        # Step 4. Create fake hgt file in tempfolder
        self.write_log(f'Creating fake elevation file with constant elevation = {height} m')

        hgtfilename = self.airport.elevation_filename

        with open(os.path.join(tgworkdir.name, hgtfilename), "wb") as hgtfile:
            # Thanks to https://github.com/SurferTim/HGTEditor for showing how to manipulate .hgt format
            array = (np.ones((1201, 1201))*int(height)).astype(">i2")
            hgtfile.write(array)

        self.progressbar.step(10)

        self.update()

        # Step 5. Run terragear docker container in detached shell mode
        self.write_log('Running terragear container')
        runstr = f'docker run -v {tgworkdir.name}:/terragear-work/ -dit --name terragear flightgear/terragear:ws20 /bin/bash'
        self.write_log(runstr)
        docker_run_result = subprocess.run(runstr.split(), capture_output=True, text=True).stdout
        self.write_log(docker_run_result)
        self.progressbar.step(10)
        self.update()


        # Step 6. Exec hgtchop
        self.write_log('Running hgtchop')
        runstr = f'docker exec -w /terragear-work/ terragear hgtchop 3 {hgtfilename} work/elev'
        self.write_log(runstr)
        hgtchop_result = subprocess.run(runstr.split(), capture_output=True, text=True).stdout.split('\n')
        self.write_log(f'Hgtchop generated {len(hgtchop_result)} lines.')
        self.progressbar.step(10)
        self.update()


        # Step 7. Exec terrafit
        self.write_log('Running terrafit')
        runstr = 'docker exec -w /terragear-work/ terragear terrafit work/elev'
        self.write_log(runstr)
        terrafit_result = subprocess.run(runstr.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.split('\n')
        self.write_log(f"Terrafit generated {len(terrafit_result)} lines.")
        self.progressbar.step(10)
        self.update()

        # Step 8. Exec genapts
        self.write_log('Running genapts')
        runstr = f'docker exec -w /terragear-work/ terragear genapts850 --threads --input={self.airport.icao}.dat --work=./work --dem-path=elev'
        self.write_log(runstr)
        genapts_result = subprocess.run(runstr.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.split('\n')
        self.write_log(f"Genapts generated {len(genapts_result)} lines.")
        self.write_log("Last 5 lines:\n")
        self.write_log("\n".join(genapts_result[-5:]))
        self.progressbar.step(10)
        self.update()

        self.write_log('Moving generated airport to the scenery folder')
        # Step 9. Create Terrain subfolder
        if not os.path.exists(os.path.join(output_folder_path, "Terrain")):
            os.makedirs(os.path.join(output_folder_path, "Terrain"))

        # Step 10. Copy all files from tempfolder/work/AirportObj to output_folder_path/Terrain

        shutil.copytree(os.path.join(tgworkdir.name, "work", "AirportObj"),
                        os.path.join(output_folder_path, "Terrain"), dirs_exist_ok=True)
        self.progressbar.step(10)

        # Step 11. Rename .ind file to .stg
        folder1, folder2 = self.airport.expected_folders
        expected_path = os.path.join(output_folder_path, "Terrain", folder1, folder2)
        if not os.path.exists(expected_path):
            ls1 = os.listdir(os.path.join(output_folder_path, "Terrain"))[0]
            ls2 = os.listdir(os.path.join(output_folder_path, "Terrain", ls1))[0]
            self.write_log(f'!!! Expected path: {folder1}/{folder2}, found path {ls1}/{ls2}')
            self.write_log(f'Airport will possibly be at sea level. Contact the developer of this software!')
            real_path = os.path.join(output_folder_path, "Terrain", ls1, ls2)
        else:
            real_path = expected_path

        ind_filename = [i for i in os.listdir(real_path) if i.endswith(".ind")][0]
        new_name = ind_filename[:-4] + ".stg"

        shutil.move(os.path.join(real_path, ind_filename),
                    os.path.join(real_path, new_name))
        self.progressbar.step(8)
        self.update()

        # Cleanup:
        # Cleanup step 1: kill docker container. check with docker ps -a
        self.write_log('Killing terragear container')
        subprocess.run(['docker', 'kill', 'terragear'])
        subprocess.run(['docker', 'rm', 'terragear'])
        self.progressbar.step(1)
        self.update()

        # Cleanup step 2: remove temporary folder
        self.write_log('Removing temporary folder')
        del tgworkdir
        self.progressbar.step(1)

        self.write_log(f'\nFinished. Load your scenery via --fg-scenery={output_folder_path} or add it in Launcher/Addons')
        self.enable_all_buttons()


    def parse_airport_data(self):
        dat_file_path = self.dat_file_entry.get()
        with open(dat_file_path, "r") as file:
            file_contents = file.read()

        dat_version = int(file_contents.split("\n")[1].split()[0])
        if dat_version < 1000 or dat_version > 1100:
            self.write_log("Error: This .dat file is not supported.")
            self.write_log(f"This dat file is version {dat_version}. Supported versions are 10** and 1100")
            return

        matches = re.findall(REGEX_AIRPORT, file_contents, re.MULTILINE)

        if len(matches) == 0 or len(matches) > 1:
            self.write_log("Error: No airports in the .dat file")
            return

        if len(matches) > 1:
            self.write_log(f"Error: This .dat file contains {len(matches)} airports.")
            self.write_log("Only one airport per file can be processed.")
            return

        elevation, icao, name = matches[0]

        self.write_log(f"Name: {name}")
        self.write_log(f"ICAO: {icao}")
        self.write_log(f"Elevation: {elevation}")

        # suggest_elevation = elevation ft to m
        suggest_elevation = int(int(elevation) * 0.3048) + 1
        self.loaded_file_label["text"] = f"Current airport: {icao}. Suggested elevation: {suggest_elevation}"

        self.airport = Airport(name, icao, elevation)

        self.parse_runways(file_contents)

    def parse_runways(self, file_contents):

        # find runway string
        matches = re.findall(r"^100\s+[\d\s.-]+$", file_contents, re.MULTILINE)
        for match in matches:

            # find 2 runway ends
            rwy_ends_match = re.findall(r"\s*100\s+-?[\d.]+\s+[\d]+\s+[012]\s+[\d.]+\s+[01]\s+\d\s+[01]\s+(?P<rwy_ends>[\dLRC.\-\s]+)", match)
            rwy_ends = rwy_ends_match[0]

            # for each runway end, find lat/lon
            rwy_data_matches = re.findall(r"([\dLRC]{2,3}\s+(?P<lat>-?[\d.]+)\s+(?P<lon>-?[\d.]+)\s+(?P<whatever>[\d.]+\s*){6})", rwy_ends)
            for rmatch in rwy_data_matches:
                lat, lon = rmatch[1:3]
                lat = float(lat)
                lon = float(lon)
                self.write_log(f"Runway end detected @ {lat}, {lon}")
                self.airport.add_lat_lon(lat, lon)

        process_result = self.airport.process_lats_lons()
        if process_result:
            self.write_log(f'Suggested elevation name: {self.airport.elevation_filename}')
            self.write_log(f'Airport will appear in folders: {"/".join(self.airport.expected_folders)}')
        else:
            self.write_log('No runways detected. To process the airport you need at least 1 runway.')
            self.write_log('You will not be able to process the airport.')

    def validate_height(self, value):
        try:
            height = int(value)
            if -10000 <= height <= 10000:
                return True
            else:
                return False
        except ValueError:
            return value in ["", "-"]  # returns True on empty input

    def write_log(self, message):
        self.log_textarea.config(state=tk.NORMAL)
        self.log_textarea.insert(tk.END, message + "\n")
        self.log_textarea.config(state=tk.DISABLED)
        self.log_textarea.see("end")

    def download_image(self):
        self.disable_all_buttons()
        try:
            docker_download = subprocess.run(['docker', 'pull', 'flightgear/terragear:ws20'], capture_output=True, text=True)
            if 'Status: Downloaded newer image' in docker_download.stdout:
                self.write_log('Docker image downloaded: flightgear/terragear:ws20')
                self.enable_all_buttons()
                self.does_docker_exist = True
            else:
                self.write_log('Docker not found. Please install Docker using the following link: https://docs.docker.com/get-docker/')
        except subprocess.CalledProcessError:
            # Handle any error that occurred while running the Docker command
            self.write_log('Error occurred while downloading Docker image')


    def change_state_all_buttons(self, state=tk.DISABLED):
        self.process_button["state"] = state
        self.dat_file_button["state"] = state
        self.output_folder_button["state"] = state

        #change state of all inputs
        self.height_entry["state"] = state
        self.dat_file_entry["state"] = state
        self.output_folder_entry["state"] = state

    def disable_all_buttons(self):
        self.change_state_all_buttons(tk.DISABLED)

    def enable_all_buttons(self):
        self.change_state_all_buttons(tk.NORMAL)

if __name__ == '__main__':
    root = tk.Tk()
    root.option_add('*foreground', 'black')
    root.option_add('*activeForeground','black')
    app = App(master=root)
    app.mainloop()
