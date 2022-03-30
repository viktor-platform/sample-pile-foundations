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
from viktor.parametrization import ChildEntityOptionField
from viktor.parametrization import DownloadButton
from viktor.parametrization import IsNotNone
from viktor.parametrization import Lookup
from viktor.parametrization import NumberField
from viktor.parametrization import Parametrization
from viktor.parametrization import Section
from viktor.parametrization import Step
from viktor.parametrization import Tab
from viktor.parametrization import Text


class ProjectParametrization(Parametrization):
    step_1 = Step("Step 1 Select and Analyze CPT",
                  views=["visualize_map", "visualize_cpt", "visualize_dfoundations_results"])

    step_1.cpt = Tab("Select CPT")
    step_1.cpt.cpt_settings = Section("CPT settings")
    step_1.cpt.cpt_settings.text = Text("Select a CPT from the uploaded .GEF files.")
    step_1.cpt.cpt_settings.cpt_selection = ChildEntityOptionField("Select CPT", entity_type_names=['CPTFile'])
    step_1.cpt.friction = Section("Friction zones")
    step_1.cpt.friction.text = Text("Set boundaries for positive and negative skin friction zones")
    step_1.cpt.friction.top_positive_friction_zone = NumberField("Top of Positive Friction Zone", suffix="m",
                                                                 default=-1.0,
                                                                 visible=IsNotNone(
                                                                     Lookup("step_1.cpt.cpt_settings.cpt_selection")))
    step_1.cpt.friction.bottom_negative_friction_zone = NumberField("Bottom of Negative Friction Zone", suffix="m",
                                                                    default=-5.0,
                                                                    visible=IsNotNone(Lookup(
                                                                        "step_1.cpt.cpt_settings.cpt_selection")))
    step_1.d_foundations = Tab("D-Foundations")
    step_1.d_foundations.downloads = Section("Downloads")
    step_1.d_foundations.downloads.text = Text("Download input or output files for D-Foundations Analysis")
    step_1.d_foundations.downloads.download_btn_input = DownloadButton(
        "Input .foi", "get_download_input",
        longpoll=True, visible=IsNotNone(Lookup(
            'step_1.cpt.cpt_settings.cpt_selection')))
    step_1.d_foundations.downloads.download_btn_output = DownloadButton("Output .fod", "get_download_output",
                                                                        longpoll=True,
                                                                        visible=IsNotNone(Lookup(
                                                                            'step_1.cpt.cpt_settings.cpt_selection')))

    step_2 = Step("Step 2 Create and Analyze Foundation",
                  views=['visualize_foundation', 'visualize_scia_results'])

    step_2.geometry = Tab("Create Foundation Geometry")

    step_2.geometry.slab = Section("Slab")
    step_2.geometry.slab.text = Text("Set slab geometry")

    step_2.geometry.slab.width_x = NumberField("Width in x", suffix="mm", default=6000)
    step_2.geometry.slab.width_y = NumberField("Width in y", suffix="mm", default=5000)
    step_2.geometry.slab.thickness = NumberField("Thickness", suffix="mm", default=500)

    step_2.geometry.piles = Section("Piles")
    step_2.geometry.piles.text = Text("Set pile geometry")
    step_2.geometry.piles.width = NumberField("Pile Width", suffix="mm", default=250)
    step_2.geometry.piles.length = NumberField("Length", suffix="m", default=13)

    step_2.loads = Tab("Load")
    step_2.loads.input = Section("Input")
    step_2.loads.input.text = Text("Input the load applied on the slab")
    step_2.loads.input.uniform_load = NumberField("Uniform load", suffix="kN/m2", default=1)

    step_2.downloads = Tab("SCIA Downloads")
    step_2.downloads.input = Section("Input")
    step_2.downloads.input.input_xml_btn = DownloadButton("Input .xml", method="download_scia_input_xml")
    step_2.downloads.input.input_def_btn = DownloadButton("Input .def", method="download_scia_input_def")
    step_2.downloads.input.input_esa_btn = DownloadButton("Input .esa", method="download_scia_input_esa")
    step_2.downloads.output = Section("Output")
    step_2.downloads.output.output_xml_btn = DownloadButton("Output .xml", method="download_scia_output_xml")

    step_3 = Step("Step 3 Visualize Combined Results", views=['visualize_intersection'])
