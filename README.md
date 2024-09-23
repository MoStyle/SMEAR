# SMEAR: Stylized Motion Exaggeration with ARt-direction

SMEAR is a 3D animation stylization Blender add-on, aimed at creation and customization of smear frames such as elongated in-betweens, multiple in-betweens and motion lines.

The system is developed as part of the [MoStyle ANR Project](https://mostyle.github.io/) by Jean Basset, Pierre Bénard and Pascal Barla. It is described in the following publication:
[SMEAR: Stylized Motion Exaggeration with ARt-direction](https://hal.science/hal-04576817v1/document). Jean Basset, Pierre Bénard, Pascal Barla. Siggraph 2024 Conference Papers

## Releases

### Latest

**[V1.1](https://github.com/MoStyle/SMEAR/releases/tag/v1_1)**: Updated add-on for Blender 4.2.0 LTS, with improved UI and simplified multiple effects application.

### Older

**[V1.0](https://github.com/MoStyle/SMEAR/releases/tag/v1_0)**: SMEAR add-on used in the paper [SMEAR: Stylized Motion Exaggeration with ARt-direction](https://hal.science/hal-04576817v1/document). Jean Basset, Pierre Bénard, Pascal Barla. Siggraph 2024 Conference Papers

## Installation and Use

### Installation

This add-on was developped and tested in **Blender 4.2.0** LTS.

Installation instructions:
- Download this repository as a .zip file.
- Open Blender and go to Edit->Preferences->Add-ons
- Click Install... and select the .zip file
- An add-on named Animation: Smear should appear in the list, click the checkbox to enable it

### Minimal example

This section gives step by step instruction for a minimal working example of the add-on, to recreate the Figure 3 from the paper linked above.
- Download Blender 4.2.0
  - Go to https://download.blender.org/release/Blender4.2/
  - Download blender-4.2.0-<YOUR_OPERATING_SYSTEM>
  - Run the downloaded installer and follow the installation instructions
- Download the add-on and name the zip file "SMEAR.zip"
- Download the animation fbx file at [https://jbasset.github.io/assets/Files/RepStamp/figure_3_animation.fbx](https://jbasset.github.io/assets/Files/RepStamp/figure_3_animation.fbx)
- Follow the instructions in video [https://jbasset.github.io/assets/Files/RepStamp/replicability_stamp.mp4](https://jbasset.github.io/assets/Files/RepStamp/replicability_stamp.mp4)
  
Note: As motion lines are randomly sampled on the surface, and the figure in the paper was done with an earlier version of Blender, the result for Figure 3.e is slightly different in the video, but conceptually similar.

### Instructions for use

The control panels for SMEAR should appear in the custom UI panels of Blender, in the section SMEAR.

#### Smear frame generation

This panel is used to pre-process animated objects to create smear frames, and control the parameters of this pre-process. The "Bake Smears" button runs the pre-process with the selected parameters. Default parameters will be appropiate in most use cases.

Parameters:
- The “Ignore skeleton” option can be used for articulated characters if you want smear frames to depend on the full body movement (e.g., for fast motion) instead of the skeleton.
- The "Prune Skeleton" section allows to select bones that will be ignored in the pre-processing. All vertices of these bones and their child will then be affected by their parent bones (see paper, section 3.2, last paragraph)
- The “Temporal smoothing window” parameters control the number of frames to consider for temporal smoothing to avoid temporally noisy effects. Default is N=2 and gives generally good results.
- The "Camera POV" option allows to compute smear frames depending on the motion of the object in camera space instead of in world space. Only available for simple objects with no skeleton for now.

After the pre-process ends, a Geometry Node modifier is applied to the selected object. Its parameters control the style of the smear frames, and can be accessed either through the modifier tab of the object or through the UI panels provided with SMEAR:

#### Elongated In-Betweens

This panel controls the Elongated In-Between effect, where the object is stretched along its trajectory.
Parameters:
- **Smear Length**: controls the general scale of the smear frames
- **Smear Past/Future length**: controls the scale of the smear frames in the past/future of the object trajectory
- **Weight by speed**: when enabled, weights the smear frames by the local speed multiplied by the **Speed factor**
- **Add noise pattern**: when enabled, weights the smear frames by a noise texture controlled by the **Noise Scale** factor
- **Manual Weights**: when enabled, weights the smear frames by the painted weights provided in the **Manual Weights Group** vertex group. For auto-completion of vertex groups, change Manual Weights Group through the modifier tab of the object.

#### Motion Lines

This panel controls the Motion Lines effect, where lines are created along the trajectory of randomly selected vertices of the object.
Parameters:
- **Lines Length**: controls the general length of the lines
- **Lines Past/Future Length**: controls the length of the lines in the Past/Future of the trajectory
- **Lines Offset**: offsets the starting positions of the lines
- **Seed**: random seed used to select seed points for lines
- **Probability**: probability for each vertex to be selected as a seed point for lines
- **Lines Speed threshold**: vertices going slower than this threshold will not be selected as seed points
- **Radius**: radius of the speed lines
- **Radius Slope**: vertices close to the speed threshold will have smaller radius. This parameter controls how fast the radius increases towards the **Radius** parameter value when going over the speed threshold (0 = no slope, the higher this paramater the longer the slope)
- **Lines Material**: material applied to the speed lines. Must be applied throught the modifier tab of the object.

#### Multiple In-Betweens

This panel controls the Multiple In-Between effect, where partially tranparent copies of the object are placed along its trajectory.
Parameters:
- **Future/Past Multiples**: number of multiple copies to add in the past and future of the trajectory
- **Future/Past Opacity Factor**: controls the opacity of the future/past copies. The lower this paramters, the more transparent the copies will appear.
- **Future/Past Displacement**: controls the distance each copy is displaced towards the future/past of the trajectory.
- **Overlap**: when enabled, overrides the displacement parameters and places the copies in order to have overlapping copies between adjacent frames of the animation. The **Number of Overlap** must be inferior or equal to the total number of copies (future + past)
- **Multiple Speed Threshold**: vertices going slower than this threshold will be transparent in the copies
