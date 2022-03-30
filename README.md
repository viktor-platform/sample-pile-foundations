![](https://img.shields.io/badge/SDK-v12.9.0-blue) <Please check version is the same as specified in requirements.txt>

# Pile Foundations
This sample app demonstrates the ability to analyze the performance of a pile foundation when implemented at a particular CPT. <basic one line intro here>

The first picture is an example of such a cpt file. On the left there is the input where the minimum layer thickness can be defined. 
On the right the soil layer interpretation is shown with its data.

![](resources/step1.png)

Then on picture 2 a map overview of all the cpt locations can be seen.

![](resources/step2.png)

Here is a gif doing the folowing tasks: 
- create a project
- upload a .gef file as cpt
- adjust some parameters in the cpt interpretation
- view the location of the cpt on the map

![](resources/CFT_with_robertson.gif)

## App structure <please provide if more than a single entity type is present>

```
project_folder: has projects as its children
  └─ project: has cpt files and foundations as its children
     └── cpt_file: intrepretation of a CPT file using the Robertson method  
     └── foundation: can show cpt_files on a map, can determine bearing capacity of the soil and determine reaction force of the foundation piles
```