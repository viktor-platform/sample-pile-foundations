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

import base64
import itertools
from pathlib import Path
from typing import Union

import numpy as np
from app.cpt_file.constants import DEFAULT_ROBERTSON_TABLE
from app.cpt_file.model import CPT
from urllib3.packages.six import BytesIO
from viktor import Color
from viktor import File
from viktor import UserException
from viktor.external.scia import LineSupport
from viktor.external.scia import LoadCase
from viktor.external.scia import LoadCombination
from viktor.external.scia import LoadGroup
from viktor.external.scia import Material as SciaMaterial
from viktor.external.scia import Model as SciaModel
from viktor.external.scia import OutputFileParser
from viktor.external.scia import PointSupport
from viktor.external.scia import SciaAnalysis
from viktor.external.scia import SurfaceLoad
from viktor.geometry import Line
from viktor.geometry import Material
from viktor.geometry import Point
from viktor.geometry import RectangularExtrusion
from viktor.geometry import Sphere
from viktor.utils import memoize


def create_scia_model(params, soils_and_colors: dict) -> SciaModel:
    """The SCIA model is created here"""
    model = SciaModel()
    '''
    STRUCTURE
    '''
    surface_level = soils_and_colors["surface_level"]
    # create nodes at the slab corners
    width_x = params.step_3.geometry.slab.width_x * 1e-03
    width_y = params.step_3.geometry.slab.width_y * 1e-03
    thickness = params.step_3.geometry.slab.thickness * 1e-03
    n1 = model.create_node('n1', 0, 0, surface_level)  # origin
    n2 = model.create_node('n2', 0, width_y, surface_level)
    n3 = model.create_node('n3', width_x, width_y, surface_level)
    n4 = model.create_node('n4', width_x, 0, surface_level)
    # create the concrete slab
    material = SciaMaterial(0, 'concrete_slab')
    corner_nodes = [n1, n2, n3, n4]
    slab = model.create_plane(corner_nodes, thickness, name='foundation slab', material=material)

    # create the pile nodes
    number_of_piles_x = 4
    number_of_piles_y = 3
    pile_edge_distance = 0.3
    pile_length = params.step_3.geometry.piles.length

    maximum_pile_length = soils_and_colors["top_elevation"] - soils_and_colors["bottom_elevation"]

    if pile_length > maximum_pile_length:
        raise UserException("Pile depth exceeds depth of CPT, should be smaller than "
                            + str(round(maximum_pile_length, 1)) + " m")

    start_x = pile_edge_distance
    end_x = width_x - pile_edge_distance
    x = np.linspace(start_x, end_x, number_of_piles_x)
    start_y = pile_edge_distance
    end_y = width_y - pile_edge_distance
    y = np.linspace(start_y, end_y, number_of_piles_y)
    pile_positions = np.array(list(itertools.product(x, y)))

    pile_top_nodes = []
    pile_bottom_nodes = []
    for pile_id, (pile_x, pile_y) in enumerate(pile_positions, 1):
        n_top = model.create_node(f'K:p{pile_id}_t', pile_x, pile_y, surface_level)
        n_bottom = model.create_node(f'K:p{pile_id}_b', pile_x, pile_y, surface_level - pile_length)
        pile_top_nodes.append(n_top)
        pile_bottom_nodes.append(n_bottom)

    # create pile beams
    pile_width = params.step_3.geometry.piles.width * 1e-03
    material = SciaMaterial(0, 'C30/37')
    cross_section = model.create_rectangular_cross_section('concrete_pile', material, pile_width, pile_width)
    pile_beams = []
    for pile_id, (n_top, n_bottom) in enumerate(zip(pile_top_nodes, pile_bottom_nodes), 1):
        pile_beam = model.create_beam(n_top, n_bottom, cross_section)
        pile_beams.append(pile_beam)
    '''
    SUPPORTS
    '''

    # create pile point supports
    freedom_v = (
        PointSupport.Freedom.FREE, PointSupport.Freedom.FREE, PointSupport.Freedom.FLEXIBLE,
        PointSupport.Freedom.FREE, PointSupport.Freedom.FREE, PointSupport.Freedom.FREE
    )
    kv = 400 * 1e06
    stiffness_v = (0, 0, kv, 0, 0, 0)
    for pile_id, pile_beam in enumerate(pile_beams, 1):
        n_bottom = pile_beam.end_node
        model.create_point_support(f'Sn:p{pile_id}', n_bottom, PointSupport.Type.STANDARD,
                                   freedom_v, stiffness_v, PointSupport.CSys.GLOBAL)
    # create the slab supports
    stiffness_x = 50 * 1e06
    stiffness_y = 50 * 1e06
    for edge in (1, 3):
        model.create_line_support_on_plane((slab, edge),
                                           x=LineSupport.Freedom.FLEXIBLE, stiffness_x=stiffness_x,
                                           y=LineSupport.Freedom.FREE,
                                           z=LineSupport.Freedom.FREE,
                                           rx=LineSupport.Freedom.FREE,
                                           ry=LineSupport.Freedom.FREE,
                                           rz=LineSupport.Freedom.FREE)
    for edge in (2, 4):
        model.create_line_support_on_plane((slab, edge),
                                           x=LineSupport.Freedom.FREE,
                                           y=LineSupport.Freedom.FLEXIBLE, stiffness_y=stiffness_y,
                                           z=LineSupport.Freedom.FREE,
                                           rx=LineSupport.Freedom.FREE,
                                           ry=LineSupport.Freedom.FREE,
                                           rz=LineSupport.Freedom.FREE)
    '''
    SETS
    '''
    # create the load group
    lg = model.create_load_group('LG1', LoadGroup.LoadOption.VARIABLE, LoadGroup.RelationOption.STANDARD,
                                 LoadGroup.LoadTypeOption.CAT_G)

    # create the load case
    lc = model.create_variable_load_case('LC1', 'first load case', lg, LoadCase.VariableLoadType.STATIC,
                                         LoadCase.Specification.STANDARD, LoadCase.Duration.SHORT)

    # create the load combination
    load_cases = {
        lc: 1
    }

    model.create_load_combination('C1', LoadCombination.Type.ENVELOPE_SERVICEABILITY, load_cases)
    '''
    LOADS
    '''
    # create the load
    force = params.step_3.geometry.loads.uniform_load * 1e03
    force *= -1  # in negative Z-direction
    model.create_surface_load('SF:1', lc, slab, SurfaceLoad.Direction.Z, SurfaceLoad.Type.FORCE, force,
                              SurfaceLoad.CSys.GLOBAL, SurfaceLoad.Location.LENGTH)
    return model


def create_visualization_geometries(params, scia_model: SciaModel, soils_and_colors: dict) -> list:
    """Creates geometries to be visualized in the editor"""
    global condition
    surface_level = soils_and_colors["surface_level"]
    geometries = []
    for node in scia_model.nodes:
        node_obj = Sphere(Point(node.x, node.y, node.z), params.step_3.geometry.slab.width_y * 1e-05)
        node_obj.material = Material('node', color=Color(0, 255, 0))
        geometries.append(node_obj)
    thickness = params.step_3.geometry.slab.thickness * 1e-03
    slab_width_x = params.step_3.geometry.slab.width_x / 1000
    slab_width_y = params.step_3.geometry.slab.width_y / 1000

    point_top = Point(slab_width_x / 2, slab_width_y / 2, surface_level)
    point_bottom = Point(slab_width_x / 2, slab_width_y / 2, surface_level - thickness)
    slab_obj = RectangularExtrusion(slab_width_x, slab_width_y, Line(point_top, point_bottom))
    slab_obj.material = Material('slab', threejs_roughness=1, threejs_opacity=0.3)
    geometries.append(slab_obj)

    pile_depth = surface_level - params.step_3.geometry.piles.length

    index=0
    for top_level in soils_and_colors["top_levels"]:
        if top_level < pile_depth:
            break
        index = index+1
    pile_width = params.step_3.geometry.piles.width * 1e-03
    # soil top levels and colors
    for i in range(1, index-1):
        top_level = soils_and_colors["top_levels"][i+1]
        bottom_level = soils_and_colors["top_levels"][i]
        color = soils_and_colors["colors"][i-1]
        r = color[0]
        g = color[1]
        b = color[2]
        for beam in scia_model.beams:
            point_top = Point(beam.begin_node.x, beam.begin_node.y, top_level)
            point_bottom = Point(beam.end_node.x, beam.end_node.y, bottom_level)
            beam_obj = RectangularExtrusion(pile_width, pile_width, Line(point_top, point_bottom))
            beam_obj.material = Material('beam', threejs_roughness=1, threejs_opacity=1.0, color=Color(r, g, b))
            geometries.append(beam_obj)
    top_level = soils_and_colors["top_levels"][index-1]
    bottom_level = pile_depth
    color = soils_and_colors["colors"][index]
    r = color[0]
    g = color[1]
    b = color[2]

    for beam in scia_model.beams:
        point_top = Point(beam.begin_node.x, beam.begin_node.y, top_level)
        point_bottom = Point(beam.end_node.x, beam.end_node.y, bottom_level)
        beam_obj = RectangularExtrusion(pile_width, pile_width, Line(point_top, point_bottom))
        beam_obj.material = Material('beam', threejs_roughness=1, threejs_opacity=1.0, color=Color(r, g, b))
        geometries.append(beam_obj)

    return geometries


def get_scia_input_esa() -> BytesIO:
    """Fetches model.esa input file"""
    esa_path = Path(__file__).parent / 'scia' / 'model.esa'
    scia_input_esa = BytesIO()
    with open(esa_path, "rb") as esa_file:
        scia_input_esa.write(esa_file.read())
    return scia_input_esa


def generate_scia_input(params, **kwargs):
    """Generates input files for scia analysis"""
    soils_and_colors = get_soil_colors(params)
    scia_model = create_scia_model(params, soils_and_colors)

    # create input files
    input_xml, input_def = scia_model.generate_xml_input()
    input_esa = get_scia_input_esa()
    return input_xml, input_def, input_esa, scia_model


def deserialize_string_to_file(file_content: str, return_bytesio: bool = True) -> Union[BytesIO, File]:
    """Deserializes a (JSON serializable) string back to a BytesIO file, to be used on output of a memoized function"""
    bytes_stream = base64.b64decode(file_content.encode("utf-8"))
    if return_bytesio:
        return BytesIO(bytes_stream)
    return File.from_data(bytes_stream)


def serialize_file_to_string(file: Union[BytesIO, File]) -> str:
    """Serializes a BytesIO file to a (JSON serializable) string, for memoization purposes"""
    if isinstance(file, File):
        return base64.b64encode(file.getvalue_binary()).decode("utf-8")
    return base64.b64encode(file.getvalue()).decode("utf-8")


@memoize
def run_scia(input_xml_content: str, input_def_content: str, input_esa_content: str, **kwargs):
    """Runs analysis in external SCIA module"""
    input_xml = deserialize_string_to_file(input_xml_content)
    input_def = deserialize_string_to_file(input_def_content)
    input_esa = deserialize_string_to_file(input_esa_content)
    # analyze SCIA model
    scia_analysis = SciaAnalysis(input_xml, input_def, input_esa)
    scia_analysis.execute(300)  # timeout after 5 minutes
    scia_result = scia_analysis.get_xml_output_file()
    return serialize_file_to_string(scia_result)


def scia_parser(scia_model: SciaModel, scia_result: BytesIO, params):
    """Parses Results from SCIA Analysis"""
    soils_and_colors = get_soil_colors(params)
    # parse analysis result
    parser = OutputFileParser
    result = parser.get_result(scia_result, "Reactions", parent='Combinations - C1')
    reactions = result['Nodal reactions']

    max_rz = float(max(reactions['R_z']))
    geometries = create_visualization_geometries(params, scia_model, soils_and_colors)
    return geometries, max_rz


def get_soil_colors(params, **kwargs) -> dict:
    """Obtains the soil level data accompanied with the corresponding color from the default Robertson table"""
    cpt_entity = params.step_1.cpt.cpt_selection
    cpt_instance = CPT(cpt_params=cpt_entity.last_saved_params, soils=DEFAULT_ROBERTSON_TABLE,
                       entity_id=cpt_entity.id)
    soils = []
    colors = []
    top_levels = [0]
    for layer in cpt_instance.params["soil_layout"]:
        soils.append(layer["name"])
        top_levels.append(layer["top_of_layer"])
        for soil_type in DEFAULT_ROBERTSON_TABLE:
            if layer["name"] == soil_type['ui_name']:
                color = soil_type["color"]
                colors.append(color)
    soils_and_colors = {
        "colors": colors,
        "top_levels": top_levels,
        "surface_level": cpt_instance.params['soil_layout'][0]["top_of_layer"],
        "top_elevation": cpt_instance.parsed_cpt.elevation[0] / 1000,
        "bottom_elevation": cpt_instance.parsed_cpt.elevation[-1] / 1000
    }
    return soils_and_colors
