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

from viktor.parametrization import DownloadButton
from viktor.parametrization import IsNotNone
from viktor.parametrization import Lookup
from viktor.parametrization import NumberField
from viktor.parametrization import Parametrization
from viktor.parametrization import Section
from viktor.parametrization import SiblingEntityOptionField
from viktor.parametrization import Step
from viktor.parametrization import Tab
from viktor.parametrization import Text


class FoundationParametrization(Parametrization):
    step_1 = Step("Select CPT",
                  views=["visualize_map"])

    step_1.cpt = Tab("Input")
    step_1.cpt.text = Text("Select a CPT from the uploaded .GEF files.")
    step_1.cpt.cpt_selection = SiblingEntityOptionField("CPT", entity_type_names=['CPTFile'])
    step_2 = Step("Analyze CPT", views=['visualize_cpt', 'visualize_dfoundations_results'])
    step_2.friction = Tab("Friction zones")
    step_2.friction.text = Text("Set boundaries for positive and negative skin friction zones")
    step_2.friction.top_positive_friction_zone = NumberField("Top of Positive Friction Zone", suffix="m",
                                                             default=-1.0,
                                                             visible=IsNotNone(
                                                                 Lookup("step_1.cpt.cpt_selection")))
    step_2.friction.bottom_negative_friction_zone = NumberField("Bottom of Negative Friction Zone", suffix="m",
                                                                default=-5.0,
                                                                visible=IsNotNone(Lookup(
                                                                    "step_1.cpt.cpt_selection")))
    step_2.d_foundations = Tab("D-Foundations")
    step_2.d_foundations.text = Text("Download input or output files for D-Foundations Analysis")
    step_2.d_foundations.download_btn_input = DownloadButton(
        "Input .foi", "get_download_input",
        longpoll=True, visible=IsNotNone(Lookup(
            'step_1.cpt.cpt_selection')))
    step_2.d_foundations.download_btn_output = DownloadButton("Output .fod", "get_download_output",
                                                              longpoll=True,
                                                              visible=IsNotNone(Lookup(
                                                                  'step_1.cpt.cpt_selection')))

    step_3 = Step("Create Foundation",
                  views=['visualize_foundation'])

    step_3.geometry = Tab("Create Foundation Geometry")

    step_3.geometry.slab = Section("Slab")
    step_3.geometry.slab.text = Text("Set slab geometry")

    step_3.geometry.slab.width_x = NumberField("Width in x", suffix="mm", default=6000)
    step_3.geometry.slab.width_y = NumberField("Width in y", suffix="mm", default=5000)
    step_3.geometry.slab.thickness = NumberField("Thickness", suffix="mm", default=500)

    step_3.geometry.piles = Section("Piles")
    step_3.geometry.piles.text = Text("Set pile geometry")
    step_3.geometry.piles.width = NumberField("Pile Width", suffix="mm", default=250)

    step_3.geometry.piles.length = NumberField("Length", suffix="m", default=10)

    step_3.geometry.loads = Section("Load")
    step_3.geometry.loads.text = Text("Input the load applied on the slab")
    step_3.geometry.loads.uniform_load = NumberField("Uniform load", suffix="kN/m2", default=1)

    step_4 = Step("Analyze Foundation", views=['visualize_scia_results'])
    step_4.downloads = Tab("SCIA Downloads")
    step_4.downloads.text = Text("Download input or output files for SCIA analysis")
    step_4.downloads.input_xml_btn = DownloadButton("Input .xml", method="download_scia_input_xml")
    step_4.downloads.input_def_btn = DownloadButton("Input .def", method="download_scia_input_def")
    step_4.downloads.input_esa_btn = DownloadButton("Input .esa", method="download_scia_input_esa")
    step_4.downloads.output_xml_btn = DownloadButton("Output .xml", method="download_scia_output_xml")

    step_5 = Step("Visualize Combined Results", views=['visualize_intersection'])
