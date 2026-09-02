# Evaluation base photos — sources and licences

Twelve real photographs of photovoltaic modules, downloaded from Wikimedia Commons at 1200 px
wide and committed to the repository so `make eval` runs offline and deterministically.

They are the **base** images: the harness derives every scenario from them by injecting a known
degradation, so the ground truth is exact. None of them carries a naturally occurring labelled
defect — `docs/EVALUATION.md` states what that does and does not let us claim.

| File | Source | Author | Licence |
|---|---|---|---|
| `panel_front_closeup.jpg` | [SolarCellPanel.jpg](https://commons.wikimedia.org/wiki/File:SolarCellPanel.jpg) | Raysonho @ Open Grid Scheduler / Grid Engine | [CC0](http://creativecommons.org/publicdomain/zero/1.0/deed.en) |
| `panel_front_plain.jpg` | [Solar Panel.jpg](https://commons.wikimedia.org/wiki/File:Solar_Panel.jpg) | Levan jgarkava | Public domain |
| `module_jetion.jpg` | [Dornbirn-Solar panel Jetion JTI 195 Jetion Solar-01ASD.jpg](https://commons.wikimedia.org/wiki/File:Dornbirn-Solar_panel_Jetion_JTI_195_Jetion_Solar-01ASD.jpg) | Asurnipal | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `module_et_solar_1.jpg` | [ET Solar, photovoltaic module (1).jpg](https://commons.wikimedia.org/wiki/File:ET_Solar,_photovoltaic_module_(1).jpg) | Cjp24 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `module_et_solar_2.jpg` | [ET Solar, photovoltaic module (2).jpg](https://commons.wikimedia.org/wiki/File:ET_Solar,_photovoltaic_module_(2).jpg) | Cjp24 | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `array_rooftop.jpg` | [Rooftop solar photovoltaic installation.jpg](https://commons.wikimedia.org/wiki/File:Rooftop_solar_photovoltaic_installation.jpg) | Marta Victoria | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `array_ground_mounted.jpg` | [Ground mounted solar panels.gk.jpg](https://commons.wikimedia.org/wiki/File:Ground_mounted_solar_panels.gk.jpg) | Grendelkhan | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `panel_israel_center.jpg` | [Photovoltaic panel at the National Solar Energy Center in Israel.jpg](https://commons.wikimedia.org/wiki/File:Photovoltaic_panel_at_the_National_Solar_Energy_Center_in_Israel.jpg) | David Shankbone | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0) |
| `array_warehouse.jpg` | [Solar Panel Warehouse.JPG](https://commons.wikimedia.org/wiki/File:Solar_Panel_Warehouse.JPG) | Bonvallite | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0) |
| `module_soiled_cleaning.jpg` | [Dornbirn-Photovoltaic module cleaning-13ASD.jpg](https://commons.wikimedia.org/wiki/File:Dornbirn-Photovoltaic_module_cleaning-13ASD.jpg) | Asurnipal | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `array_marine.jpg` | [Marine Solar Panel Array on Blue Start Delos.jpg](https://commons.wikimedia.org/wiki/File:Marine_Solar_Panel_Array_on_Blue_Start_Delos.jpg) | Gregory Atkinson | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |
| `modules_packed.jpg` | [Dornbirn-packed photovoltaic panels-01ASD.jpg](https://commons.wikimedia.org/wiki/File:Dornbirn-packed_photovoltaic_panels-01ASD.jpg) | Asurnipal | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0) |

Share-alike licences (CC BY-SA) apply to the photographs themselves. They are redistributed here
unmodified, with attribution; the derived scenarios the harness generates at run time are not
committed.
