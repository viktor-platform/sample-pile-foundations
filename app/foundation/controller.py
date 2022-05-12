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

import numpy as np
import plotly.graph_objects as go
from munch import Munch
from viktor.api_v1 import API
from viktor.core import UserException
from viktor.core import ViktorController
from viktor.external.scia import Model as SciaModel
from viktor.result import DownloadResult
from viktor.views import DataGroup
from viktor.views import DataItem
from viktor.views import GeometryAndDataResult
from viktor.views import GeometryAndDataView
from viktor.views import GeometryResult
from viktor.views import GeometryView
from viktor.views import MapResult
from viktor.views import MapView
from viktor.views import PlotlyAndDataResult
from viktor.views import PlotlyAndDataView
from viktor.views import PlotlyResult
from viktor.views import PlotlyView
from viktor.views import WebAndDataResult
from viktor.views import WebAndDataView
from .dfoundations_model import dfoundations_parser
from .dfoundations_model import generate_dfoundations_input
from .dfoundations_model import run_dfoundations
from .parametrization import FoundationParametrization
from .scia_model import create_scia_model
from .scia_model import create_visualization_geometries
from .scia_model import deserialize_string_to_file
from .scia_model import generate_scia_input
from .scia_model import get_scia_input_esa
from .scia_model import get_soil_colors
from .scia_model import run_scia
from .scia_model import scia_parser
from .scia_model import serialize_file_to_string
from .. import CPTFileController
from ..cpt_file.constants import DEFAULT_ROBERTSON_TABLE
from ..cpt_file.model import CPT


class FoundationController(ViktorController):
    """Controller class which acts as interface for the Sample entity type."""
    label = "Foundation"
    parametrization = FoundationParametrization

    @MapView('Map', duration_guess=2)  # Visible in step 1
    def visualize_map(self, params: Munch, entity_id: int, **kwargs) -> MapResult:
        """Visualize the MapView with all CPT locations and a polyline"""
        all_cpt_models = self.get_cpt_models(entity_id)
        cpt_features = []
        for cpt in all_cpt_models:
            cpt_features.append(cpt.get_map_point())

        return MapResult(cpt_features)

    @staticmethod
    def get_cpt_models(entity_id: int) -> list:
        """Obtains all child 'CPT File' entities"""
        cpt_file_entities = API().get_entity(entity_id).siblings(entity_type_names=['CPTFile'], include_params=True)
        all_cpt_files = [CPT(cpt_params=cpt_entity.last_saved_params, entity_id=cpt_entity.id)
                         for cpt_entity in cpt_file_entities]

        return all_cpt_files

    @WebAndDataView("GEF", duration_guess=3)  # Visible in step 1
    def visualize_cpt(self, params: Munch, **kwargs) -> WebAndDataResult:
        """Provides Visualization and Data parsed from selected CPT file"""
        if params.step_1.cpt.cpt_selection is None:
            raise UserException("No CPT selected")
        cpt_entity = params.step_1.cpt.cpt_selection
        cpt = CPT(cpt_params=cpt_entity.last_saved_params, soils=DEFAULT_ROBERTSON_TABLE, entity_id=cpt_entity.id)
        data_group = CPTFileController.get_data_group(cpt_entity.last_saved_params)
        return WebAndDataResult(html=cpt.visualize(), data=data_group)

    @PlotlyView("DFoundations Result", duration_guess=60)  # Visible in step 1
    def visualize_dfoundations_results(self, params: Munch, **kwargs) -> PlotlyResult:
        """Obtains bearing capacity of the soil by running CPT file through D-Foundations."""
        foi_file = generate_dfoundations_input(params)
        fod_file_content = run_dfoundations(foi_file.getvalue())
        parsed_results = dfoundations_parser(fod_file_content)
        fig = {
            "data": [{"type": "line", "x": parsed_results["Bearing Strength GT1B"], "y": parsed_results["Depth"]}],
            "layout": {"title": {"text": "Bearing Capacity vs Depth"},
                       "xaxis": {"title": {"text": "Bearing Capacity [N]"}},
                       "yaxis": {"title": {"text": "Depth [m]"}}}
        }
        return PlotlyResult(fig)

    @staticmethod  # Visible in step 1
    def get_download_input(params, **kwargs) -> DownloadResult:
        """Provides ability to download input file for D-Foundations"""
        dfoundations_input_file = generate_dfoundations_input(params)
        return DownloadResult(file_content=dfoundations_input_file, file_name='input.foi')

    @staticmethod  # Visible in step 1
    def get_download_output(params, **kwargs) -> DownloadResult:
        """Provides ability to download output file for D-Foundations"""
        foi_file = generate_dfoundations_input(params)
        fod_file_content = run_dfoundations(foi_file.getvalue())
        return DownloadResult(file_content=fod_file_content, file_name='output.fod')

    @GeometryView("3D", duration_guess=1)  # Visible in step 2
    def visualize_foundation(self, params, **kwargs) -> GeometryResult:
        """Provides Visualization of the Foundation Geometry as specified in the editor"""
        soils_and_colors = get_soil_colors(params)
        scia_model = create_scia_model(params, soils_and_colors)
        geometries = create_visualization_geometries(params, scia_model, soils_and_colors)
        return GeometryResult(geometries)

    @staticmethod  # Visible in step 2
    def download_scia_input_esa(params, **kwargs) -> DownloadResult:
        """Provides ability to download SCIA input file .esa"""
        scia_input_esa = get_scia_input_esa()
        filename = "model.esa"
        return DownloadResult(scia_input_esa, filename)

    @staticmethod  # Visible in step 2
    def download_scia_input_xml(params, **kwargs) -> DownloadResult:
        """Provides ability to download SCIA input file .xml"""
        soils_and_colors = get_soil_colors(params)
        scia_model = create_scia_model(params, soils_and_colors)
        input_xml, _ = scia_model.generate_xml_input()

        return DownloadResult(input_xml, 'test.xml')

    @staticmethod  # Visible in step 2
    def download_scia_input_def(params, **kwargs) -> DownloadResult:
        """Provides ability to download SCIA input file .def"""
        m = SciaModel()
        _, input_def = m.generate_xml_input()
        return DownloadResult(input_def, 'viktor.xml.def')

    @staticmethod  # Visible in step 2
    def download_scia_output_xml(params, **kwargs) -> DownloadResult:
        """Provides ability to download SCIA input file .def"""
        input_xml, input_def, input_esa, scia_model = generate_scia_input(params)
        input_xml_content = serialize_file_to_string(input_xml)
        input_def_content = serialize_file_to_string(input_def)
        input_esa_content = serialize_file_to_string(input_esa)
        scia_result = run_scia(input_xml_content, input_def_content, input_esa_content)
        return DownloadResult(deserialize_string_to_file(scia_result), 'output.xml')

    @GeometryAndDataView("SCIA result", duration_guess=60)  # Visible in step 2
    def visualize_scia_results(self, params, **kwargs) -> GeometryAndDataResult:
        """Obtains maximum reaction force by running foundation geometry through SCIA.
         Also visualizes foundation geometry"""
        input_xml, input_def, input_esa, scia_model = generate_scia_input(params)
        input_xml_content = serialize_file_to_string(input_xml)
        input_def_content = serialize_file_to_string(input_def)
        input_esa_content = serialize_file_to_string(input_esa)
        scia_result = run_scia(input_xml_content, input_def_content, input_esa_content)
        scia_result = deserialize_string_to_file(scia_result)
        geometries, max_rz = scia_parser(scia_model, scia_result, params)
        data_result = DataGroup(
                DataItem('Maximum pile reaction', max_rz, suffix='N', number_of_decimals=2))
        return GeometryAndDataResult(geometries, data_result)

    @PlotlyAndDataView("SCIA & D-Foundations Intersection", duration_guess=60)  # Visible in step 3
    def visualize_intersection(self, params, **kwargs) -> PlotlyAndDataResult:
        """Provides visualization of D-Foundations with the max reaction force and required pile tip level"""
        cpt_entity = params.step_1.cpt.cpt_selection
        cpt_instance = CPT(cpt_params=cpt_entity.last_saved_params, soils=DEFAULT_ROBERTSON_TABLE,
                           entity_id=cpt_entity.id)
        surface_level = cpt_instance.params['soil_layout'][0]["top_of_layer"]
        input_xml, input_def, input_esa, scia_model = generate_scia_input(params)
        input_xml_content = serialize_file_to_string(input_xml)
        input_def_content = serialize_file_to_string(input_def)
        input_esa_content = serialize_file_to_string(input_esa)
        scia_result = run_scia(input_xml_content, input_def_content, input_esa_content)
        scia_result = deserialize_string_to_file(scia_result)
        _, max_rz = scia_parser(scia_model, scia_result, params)
        foi_file = generate_dfoundations_input(params)
        fod_file_content = run_dfoundations(foi_file.getvalue())
        parsed_results = dfoundations_parser(fod_file_content)
        closest_bearing_strength = min(parsed_results["Bearing Strength GT1B"], key=lambda x: abs(x - max_rz))
        index_closest_bearing_strength = parsed_results["Bearing Strength GT1B"].index(closest_bearing_strength)
        required_pile_tip_level = parsed_results["Depth"][index_closest_bearing_strength]
        data_result = DataGroup(
                DataItem('Max Reaction Force', max_rz, suffix='N', number_of_decimals=1),
                DataItem('Required Pile Tip Level', required_pile_tip_level, suffix='m', number_of_decimals=1),
                DataItem('Required Pile Length', required_pile_tip_level - surface_level, suffix='m',
                         number_of_decimals=1)
        )

        fig = go.Figure(
            data=[
                go.Line(x=parsed_results["Bearing Strength GT1B"], y=parsed_results["Depth"], name="Bearing Strength")],
            layout=go.Layout(  # title=go.layout.Title(text="Intersection"),
                xaxis=go.layout.XAxis(title="Force [N]"),
                yaxis=go.layout.YAxis(title="Depth [m]"))
        )
        fig.add_trace(go.Line(name="Reaction Force",
                              x=max_rz * np.ones(100),
                              y=np.linspace(min(parsed_results["Depth"]), 0, 100)))
        fig.add_trace(go.Line(name="Required Pile Tip Level",
                              x=np.linspace(min(parsed_results["Bearing Strength GT1B"]),
                                            max(parsed_results["Bearing Strength GT1B"]), 100),
                              y=np.ones(100) * required_pile_tip_level))
        return PlotlyAndDataResult(fig.to_json(), data_result)
