# FlightGear Airport Sketcher

This script allows you to convert airport from X-Plane .dat format to FlightGear scenery format.

Since this program does not rebuild terrain, your resulting airport will be a flat plane laying over the scenery. If the nearby scenery is not a perfect flat plane, some parts of your airport will hang in the air. Therefore, this tool only "sketches" the airport and cannot be a complete substitute to full TerraGear pipeline. However, it may be useful for people that want to quickly get a rough airport in their program.

![](docs-images/2023-08-06_23-14.png)

![](docs-images/fgfs-20230806201655.png)

# Dependencies

1. This program utilizes Docker TerraGear image to convert the airport data. Therefore, you need to have Docker installed. Additionally, on Linux, it should be able to start without sudo: see [this page](https://docs.docker.com/engine/install/linux-postinstall/) if you can only run docker with sudo.
2. This program has been written for FlightGear 2020.3 and tested on version 2020.3.18.
3. This program has been tested with python==3.11.4, pexpect==4.8.0, numpy==1.25.2.
