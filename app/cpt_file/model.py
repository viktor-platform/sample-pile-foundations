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
from math import floor

from munch import Munch
from munch import munchify
from munch import unmunchify
from plotly import graph_objects as go
from plotly.subplots import make_subplots
from viktor import UserException
from viktor.geo import GEFData
from viktor.geo import SoilLayout
from viktor.geometry import RDWGSConverter
from viktor.views import MapEntityLink
from viktor.views import MapPoint
from .soil_layout_conversion_functions import convert_input_table_field_to_soil_layout


class CPT:
    """"CPT model used for visualizing the soil layout"""

    def __init__(self, cpt_params, entity_id=None, **kwargs):
        params = unmunchify(cpt_params)
        self.params = params
        self.parsed_cpt = GEFData(self.filter_nones_from_params_dict(params))
        self.soil_layout_original = SoilLayout.from_dict(params['soil_layout_original'])
        self.entity_id = entity_id

    @property
    def soil_layout(self) -> SoilLayout:
        """Returns a soil layout based on the input table"""
        return convert_input_table_field_to_soil_layout(self.params['bottom_of_soil_layout_user'],
                                                        self.params['soil_layout'])

    @property
    def entity_link(self) -> MapEntityLink:
        """Returns a MapEntity link to the GEF entity, which is used in the MapView of the Project entity"""
        return MapEntityLink(self.params['cpt_name'], self.entity_id)

    @staticmethod
    def filter_nones_from_params_dict(raw_dict) -> dict:
        """Removes all rows which contain one or more None-values"""
        rows_to_be_removed = []
        for row_index, items in enumerate(zip(*raw_dict['measurement_data'].values())):
            if None in items:
                rows_to_be_removed.append(row_index)
        for row in reversed(rows_to_be_removed):
            for signal in raw_dict['measurement_data'].keys():
                del raw_dict['measurement_data'][signal][row]
        return raw_dict

    @property
    def wgs_coordinates(self) -> Munch:
        """Returns a dictionary of the lat lon coordinates to be used in geographic calculations"""
        # chekc if coordinates are present, else raise error to user
        if not hasattr(self.parsed_cpt, 'x_y_coordinates') or None in self.parsed_cpt.x_y_coordinates:
            raise UserException(f"CPT {self.params['cpt_name']} has no coordinates: please check the GEF file")

        # do conversion and return
        lat, lon = RDWGSConverter.from_rd_to_wgs(self.parsed_cpt.x_y_coordinates)
        return munchify({"lat": lat, "lon": lon})

    def get_map_point(self) -> MapPoint:
        """Returns a MapPoint object"""
        return MapPoint(self.wgs_coordinates.lat, self.wgs_coordinates.lon, title=self.params['cpt_name'],
                        entity_links=[self.entity_link])

    def visualize(self) -> StringIO:
        """Creates an interactive plot using plotly, showing the same information as the static visualization"""
        fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.00, column_widths=[3.5, 1.5, 2],
                            subplot_titles=("Cone Resistance", "Friction ratio", "Soil Layout"))

        self.add_qc_and_rf_to_fig(fig)  # add left side of the figure: Qc and Rf plot
        self.add_soil_layout_to_fig(fig)   # add right side of the figure: original and interpreted soil layout
        self.add_phreatic_level_line_to_fig(fig)  # add phreatic line to both figures
        self.update_fig_layout(fig)  # format axis and grids before showing to the user

        return StringIO(fig.to_html())

    def update_fig_layout(self, fig):
        """Updates layout of the figure and formats the grids"""
        fig.update_layout(barmode='stack', template='plotly_white', legend=dict(x=1.15, y=0.5))
        fig.update_annotations(font_size=12)
        # Format axes and grids per subplot
        standard_grid_options = dict(showgrid=True, gridwidth=1, gridcolor='LightGrey')
        standard_line_options = dict(showline=True, linewidth=2, linecolor='LightGrey')

        # update x-axis for Qc
        fig.update_xaxes(row=1, col=1, **standard_line_options, **standard_grid_options,
                         range=[0, 30], tick0=0, dtick=5, title_text="qc [MPa]", title_font=dict(color='mediumblue'))
        # update x-axis for Rf
        fig.update_xaxes(row=1, col=2, **standard_line_options, **standard_grid_options,
                         range=[9.9, 0], tick0=0, dtick=5, title_text="Rf [%]", title_font=dict(color='red'))

        # update all y axis to ensure they line up
        fig.update_yaxes(row=1, col=1, **standard_grid_options, title_text="Depth [m] w.r.t. NAP",
                         tick0=floor(self.parsed_cpt.elevation[-1] / 1e3) - 5, dtick=1)   # for Qc

        fig.update_yaxes(row=1, col=2, **standard_line_options, **standard_grid_options,  # for Rf
                         tick0=floor(self.parsed_cpt.elevation[-1] / 1e3) - 5, dtick=1)

        fig.update_yaxes(row=1, col=3, **standard_line_options,                           # for soil layouts
                         tick0=floor(self.parsed_cpt.elevation[-1] / 1e3) - 5, dtick=1,
                         showticklabels=True, side='right')

    def add_phreatic_level_line_to_fig(self, fig):
        """Add dashed blue line representing phreatic level"""
        fig.add_hline(y=self.params['ground_water_level'], line=dict(color='Blue', dash='dash', width=1),
                      row='all', col='all')

    def add_soil_layout_to_fig(self, fig):
        """Add bars for each soil type separately in order to be able to set legend labels"""
        unique_soil_types = {layer.soil.properties.ui_name for layer in [*self.soil_layout_original.layers,
                                                                         *self.soil_layout.layers]}
        for ui_name in unique_soil_types:
            original_layers = [layer for layer in self.soil_layout_original.layers
                               if layer.soil.properties.ui_name == ui_name]
            interpreted_layers = [layer for layer in self.soil_layout.layers
                                  if layer.soil.properties.ui_name == ui_name]
            soil_type_layers = [*original_layers, *interpreted_layers]  # have a list of all soils used in both figures

            # add the bar plots to the figures
            fig.add_trace(go.Bar(name=ui_name,
                                 x=['Original'] * len(original_layers) + ['Interpreted'] * len(interpreted_layers),
                                 y=[-layer.thickness * 1e-3 for layer in soil_type_layers],
                                 width=0.5,
                                 marker_color=[f"rgb{layer.soil.color.rgb}" for layer in soil_type_layers],
                                 hovertext=[f"Soil Type: {layer.soil.properties.ui_name}<br>"
                                            f"Top of layer: {layer.top_of_layer * 1e-3:.2f}<br>"
                                            f"Bottom of layer: {layer.bottom_of_layer * 1e-3:.2f}"
                                            for layer in soil_type_layers],
                                 hoverinfo='text',
                                 base=[layer.top_of_layer * 1e-3 for layer in soil_type_layers]),
                          row=1, col=3)

    def add_qc_and_rf_to_fig(self, fig):
        """Add Qc and Rf plot."""

        fig.add_trace(  # Add the qc curve
            go.Scatter(name='Cone Resistance',
                       x=self.parsed_cpt.qc,
                       y=[el * 1e-3 for el in self.parsed_cpt.elevation],
                       mode='lines',
                       line=dict(color='mediumblue', width=1),
                       legendgroup="Cone Resistance"),
            row=1, col=1
        )

        fig.add_trace(   # Add the Rf curve
            go.Scatter(name='Friction ratio',
                       x=[rfval * 100 if rfval else rfval for rfval in self.parsed_cpt.Rf],
                       y=[el * 1e-3 if el else el for el in self.parsed_cpt.elevation],
                       mode='lines',
                       line=dict(color='red', width=1),
                       legendgroup="Friction ratio"),
            row=1, col=2
        )

