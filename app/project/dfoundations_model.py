"""Copyright (c) 2022 VIKTOR B.V.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

VIKTOR B.V. PROVIDES THIS SOFTWARE ON AN "AS IS" BASIS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from io import StringIO
from pathlib import Path

import geolib.models.dfoundations.piles
import geolib.models.dfoundations.profiles
from app.cpt_file.constants import DEFAULT_ROBERTSON_TABLE
from app.cpt_file.model import CPT
from geolib.geometry import Point
from geolib.models.dfoundations import profiles
from geolib.models.dfoundations.dfoundations_model import BearingPilesModel
from geolib.models.dfoundations.dfoundations_model import CalculationOptions
from geolib.models.dfoundations.dfoundations_model import CalculationType
from geolib.models.dfoundations.dfoundations_model import DFoundationsModel
from geolib.soils import Soil
from geolib.soils import SoilType
from viktor import File
from viktor import UserException
from viktor.external.dfoundations import DFoundationsAnalysis
from viktor.external.dfoundations import OutputFileParser
from viktor.utils import memoize


@memoize
def run_dfoundations(foi_file_content: str, **kwargs) -> str:
    """Sends input file through D-Foundations and obtains output file"""
    foi_file = File.from_data(foi_file_content)
    dfoundations_analysis = DFoundationsAnalysis(input_file=foi_file)
    dfoundations_analysis.execute(timeout=300)
    fod_file = dfoundations_analysis.get_output_file(as_file=True)
    return fod_file.getvalue()


def generate_dfoundations_input(params, **kwargs) -> File:
    """Generates input file for D-Foundations"""
    cpt_entity = params.step_1.cpt.cpt_settings.cpt_selection
    cpt_instance = CPT(cpt_params=cpt_entity.last_saved_params, soils=DEFAULT_ROBERTSON_TABLE,
                       entity_id=cpt_entity.id)

    elevation = cpt_instance.parsed_cpt.elevation
    qc = cpt_instance.parsed_cpt.qc
    Rf = cpt_instance.parsed_cpt.Rf

    top_level_cpt = cpt_instance.params['soil_layout'][0]["top_of_layer"]

    measured_data = [{"z": elevation / 1000., "qc": qc, "Rf": Rf}
                     for elevation, qc, Rf in zip(elevation, qc, Rf)
                     if elevation < top_level_cpt * 1000]

    dfoundations_model = DFoundationsModel()

    model_options = BearingPilesModel(
        is_rigid=False, factor_xi3=9
    )
    calculation_options = CalculationOptions(
        calculationtype= CalculationType.VERIFICATION_DESIGN,
        cpt_test_level=-14.0,
        trajectory_begin=-0.0,
        trajectory_end=-25.0,
        trajectory_interval=0.1
    )
    dfoundations_model.set_model(model_options, calculation_options)

    cpt = profiles.CPT(
        cptname=cpt_instance.parsed_cpt.name,
        groundlevel=cpt_instance.parsed_cpt.ground_level_wrt_reference / 1000,
        measured_data=measured_data,
        timeorder_type=profiles.TimeOrderType.CPT_BEFORE_AND_AFTER_INSTALL,
    )

    excavation_level = 1.0
    excavation = profiles.Excavation(excavation_level=excavation_level)

    location_cpt = profiles.Point(x=cpt_instance.parsed_cpt.x_y_coordinates[0],
                                  y=cpt_instance.parsed_cpt.x_y_coordinates[1])

    for soil_type in DEFAULT_ROBERTSON_TABLE[1:10]:
        soil = Soil()
        soil_name = soil_type["ui_name"]
        soil_name = soil_name.replace(" tot ", "-")
        soil.name = soil_name.replace("fijnkorrelig", "fijn")
        if soil_name[:4] == 'Klei':
            soil.soil_type_nl = SoilType.CLAY
        elif soil_name[:5] == 'Grond':
            soil.soil_type_nl = SoilType.GRAVEL
        elif soil_name[:4] == 'Leem':
            soil.soil_type_nl = SoilType.LOAM
        elif soil_name[:4] == 'Veen':
            soil.soil_type_nl = SoilType.PEAT
        elif soil_name[:4] == 'Zand':
            soil.soil_type_nl = SoilType.SAND
        else:
            raise UserException("Unidentifiable Soil Type included in CPT")

        soil.undrained_parameters.undrained_shear_strength = 20
        soil.mohr_coulomb_parameters.friction_angle = soil_type["phi"]
        soil.soil_weight_parameters.unsaturated_weight = soil_type["gamma_dry"]
        soil.soil_weight_parameters.saturated_weight = soil_type["gamma_wet"]
        dfoundations_model.add_soil(soil)

    materials = []
    top_levels = []

    for i in range(len(cpt_instance.params['soil_layout'])):
        material = cpt_instance.params['soil_layout'][i]['name']
        material = material.replace(" tot ", "-")
        material = material.replace("fijnkorrelig", "fijn")
        materials.append(material)
        top_levels.append(cpt_instance.params['soil_layout'][i]['top_of_layer'])

    layers = [{"material": material, "top_level": top_level}
              for material, top_level in zip(materials, top_levels)]

    phreatic_level = cpt_instance.params["ground_water_level"]
    top_of_positive_skin_friction = params.step_1.cpt.friction.top_positive_friction_zone
    bottom_of_negative_skin_friction = params.step_1.cpt.friction.bottom_negative_friction_zone

    profile = profiles.Profile(
        name=cpt_instance.parsed_cpt.name,
        location=location_cpt,
        phreatic_level=phreatic_level,
        pile_tip_level=-params.step_2.geometry.piles.length,  # Don't know yet?
        cpt=cpt,
        excavation=excavation,
        top_of_positive_skin_friction=top_of_positive_skin_friction,
        bottom_of_negative_skin_friction=bottom_of_negative_skin_friction,
        layers=layers)

    if top_of_positive_skin_friction > top_level_cpt:
        raise UserException(
            "CPT DKM014 : Top of positive skin friction lies above surface level which is not allowed")
    elif top_of_positive_skin_friction > excavation_level:
        raise UserException(
            "CPT DKM014 : Top of positive skin friction lies above surface level which is not allowed")

    dfoundations_model.add_profile(profile)

    piles = geolib.models.dfoundations.piles

    # Add Bearing Pile
    location = piles.BearingPileLocation(
        point=Point(x=1.0, y=1.0),
        pile_head_level=1,
        surcharge=1,
        limit_state_str=1,
        limit_state_service=1,
    )

    base_width = params.step_2.geometry.piles.width / 1000.
    base_length = base_width
    geometry_pile = dict(base_width=base_width, base_length=base_length)
    parent_pile = dict(
        pile_name="test",
        pile_type=piles.BasePileType.USER_DEFINED_VIBRATING,
        pile_class_factor_shaft_sand_gravel=1,  # alpha_s
        preset_pile_class_factor_shaft_clay_loam_peat=piles.BasePileTypeForClayLoamPeat.STANDARD,
        pile_class_factor_shaft_clay_loam_peat=1,  # alpha_s
        pile_class_factor_tip=1,  # alpha_p
        load_settlement_curve=piles.LoadSettlementCurve.ONE,
        user_defined_pile_type_as_prefab=False,
        use_manual_reduction_for_qc=False,
        elasticity_modulus=1e7,
        characteristic_adhesion=10,
        overrule_pile_tip_shape_factor=False,
        overrule_pile_tip_cross_section_factors=False,
    )

    pile = piles.BearingRectangularPile(**parent_pile, **geometry_pile)

    dfoundations_model.add_pile_if_unique(pile, location)

    file = File()
    path = Path(file.source)
    dfoundations_model.serialize(path)
    original_file = open(path, "r")
    lines = original_file.readlines()
    original_file.close()
    new_file = open(path, "w")
    for line in lines:
        if line[:4] == "DATE":
            new_file.write("\n")
        elif line[:4] == "TIME":
            new_file.write("\n")
        else:
            new_file.write(line)
    new_file.close()
    foi_file = file
    return foi_file


def dfoundations_parser(fod_file_content: str) -> dict:
    """Parses raw D-Foundations results into interpretable data describing bearing capacity against depth"""
    parsed_results = {}
    parser = OutputFileParser(StringIO(fod_file_content))
    # # Raw, unparsed results in the form of a string.
    raw_results = parser.raw_results
    text = raw_results.split("\n")
    depths = []
    shaft_strengths_gt1b = []
    point_strengths_gt1b = []
    total_strengths_gt1b = []
    shaft_strengths_gt2 = []
    point_strengths_gt2 = []
    total_strengths_gt2 = []

    for index, element in enumerate(text):
        if element == "[ITERATION]\r":
            depth = float(text[index + 2][:6])
            depths.append(depth)
            shaft_strength_gt1b = float(text[index + 10][:9])
            shaft_strengths_gt1b.append(shaft_strength_gt1b)
            point_strength_gt1b = float(text[index + 10][13:20])
            point_strengths_gt1b.append(point_strength_gt1b)
            total_strength_gt1b = shaft_strength_gt1b + point_strength_gt1b
            total_strengths_gt1b.append(total_strength_gt1b)
            shaft_strength_gt2 = float(text[index + 13][:9])
            shaft_strengths_gt2.append(shaft_strength_gt2)
            point_strength_gt2 = float(text[index + 13][13:20])
            point_strengths_gt2.append(point_strength_gt2)
            total_strength_gt2 = shaft_strength_gt1b + point_strength_gt2
            total_strengths_gt2.append(total_strength_gt2)
        else:
            continue

        parsed_results["Depth"] = depths
        parsed_results["Bearing Strength GT1B"] = total_strengths_gt1b
        parsed_results["Bearing Strength GT2"] = total_strengths_gt2
    return parsed_results
