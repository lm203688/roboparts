---
language:
- en
- zh
license: cc-by-4.0
library_name: datasets
tags:
- robotics
- bionic-robot
- actuators
- sensors
- embedded-systems
- llm
- robot-components
- embodied-ai
- ros2
- hardware-selection
- lerobot
- robot-ai-models
- flexible-actuators
- humanoid-robot
datasets_info:
  - config_name: default
    features:
      - name: category
        dtype: string
      - name: entities
        sequence:
          - name: name
            dtype: string
          - name: manufacturer
            dtype: string
          - name: type
            dtype: string
          - name: specs
            dtype: struct
          - name: source
            dtype: string
          - name: confidence
            dtype: float32
          - name: last_verified
            dtype: string
          - name: standard_compliance
            sequence: string
          - name: bionic_features
            sequence: string
          - name: ros2_compatible
            dtype: bool
    splits:
      - name: full
        num_bytes: 380000
        num_examples: 688
---

# RoboParts Dataset

**RoboParts** is the first structured dataset covering ten core categories of bionic robot components: actuators, flexible actuators, sensors, chips, communication protocols, large language models (LLMs), robot AI models, interfaces, platforms, and data acquisition devices. Designed for embodied intelligence research and humanoid robot development.

## Dataset Overview

| Category | Count | Key Fields |
|---|---|---|
| Actuators | 199 | Torque, speed, voltage, protocol, weight, price |
| Flexible Actuators | 21 | Flexibility, deformation, drive type, material |
| Sensors | 90 | Range, precision, type, manufacturer |
| Chips | 108 | CPU, AI performance, power, price range |
| Protocols | 64 | Speed, latency, max nodes, standard |
| LLMs | 42 | Parameters, open-source, embodied support |
| Robot AI Models | 44 | Model type, parameters, tasks, open-source |
| Interfaces | 37 | Speed, power, connector type |
| Platforms | 40 | Type, open-source, simulation support |
| Data Acquisition | 43 | Teleoperation, motion capture, tactile sensing |

**Total: 688 entities across 10 categories**

## LeRobot Ecosystem

This dataset is tagged for the [LeRobot](https://github.com/huggingface/lerobot) robotics learning ecosystem (v0.6.0+). Compatible with world model policies (VLA-JEPA, LingBot-VA, FastWAM) and reward model APIs introduced in v0.6.0. Use `tags: lerobot, robotics` to discover related models and datasets on HuggingFace.

## Data Quality

- **Standardized fields**: Every entity includes `source`, `confidence`, `last_verified`, `standard_compliance`
- **Bionic tagging**: Supports filtering for bionic actuators (SEA / flexible)
- **National standard compliance**: Tracks GB humanoid robot modular requirements
- **ROS2 compatibility**: Annotated for ROS2 compatibility
- **Continuous updates**: Collected from manufacturer datasheets, ROS2 docs, ISO/national standards

| Field | Coverage |
|---|---|
| Name | 100% |
| Manufacturer | 95% |
| Specifications | 85% |
| Price range | 70% |
| Standard compliance | 60% |

## Usage

### Direct Download

```python
from datasets import load_dataset

dataset = load_dataset("roboparts/roboparts-dataset", split="full")
```

### Python (Raw JSON)

```python
import json, requests

url = "https://roboparts.cc/api/data.json"
data = requests.get(url).json()

# Find all bionic actuators
bionic_actuators = [
    a for a in data["actuators"]
    if a.get("bionic_features") and len(a["bionic_features"]) > 0
]
```

## Smart Selection Engine

The dataset powers the online selection engine at [roboparts.cc](https://roboparts.cc):

- Input joint position, torque requirement, budget
- Automatic compatible actuator matching
- Multi-factor scoring (torque/price 30%, weight 20%, protocol match 25%, bionic 15%, standard 10%)

## Citation

```bibtex
@dataset{roboparts2026,
  title={RoboParts: A Structured Dataset for Bionic Robot Components},
  author={RoboParts Team},
  year={2026},
  url={https://roboparts.cc}
}
```

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — Free to use with attribution.

## Links

- Website: https://roboparts.cc
- GitHub: https://github.com/lm203688/roboparts
- ModelScope (public): https://www.modelscope.cn/datasets/roboparts/roboparts-data
- API Docs: https://roboparts.cc/api-pricing
