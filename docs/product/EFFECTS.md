# 效果算子完整参数

[README](../../README.md) · [Installed response](effects.json)

46 项，来自当前安装版 effects list；参数是否支持动画以每项声明为准。

## `avgblur`

```json
{
  "id": "avgblur",
  "aliases": [
    "average_blur"
  ],
  "category": "blur",
  "backend": "ffmpeg:avgblur",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "size_x": {
      "type": "number",
      "default": 2.0,
      "minimum": 1.0,
      "maximum": 1024.0
    },
    "size_y": {
      "type": "number",
      "default": 2.0,
      "minimum": 0.0,
      "maximum": 1024.0
    },
    "planes": {
      "type": "integer",
      "default": 15,
      "minimum": 0,
      "maximum": 15
    }
  },
  "limits": []
}
```

## `blur`

```json
{
  "id": "blur",
  "aliases": [
    "gaussian_blur",
    "gblur"
  ],
  "category": "blur",
  "backend": "ffmpeg:gblur",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "radius": {
      "type": "number",
      "default": 4.0,
      "minimum": 0.0,
      "maximum": 128.0
    }
  },
  "limits": [
    "radius_sets_both_sigma_and_sigmaV",
    "blur_filters_RGB_and_alpha_planes",
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "radius"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `box_blur`

```json
{
  "id": "box_blur",
  "aliases": [
    "boxblur"
  ],
  "category": "blur",
  "backend": "ffmpeg:boxblur",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "radius": {
      "type": "number",
      "default": 4.0,
      "minimum": 1.0,
      "maximum": 128.0
    },
    "power": {
      "type": "number",
      "default": 1.0,
      "minimum": 1.0,
      "maximum": 4.0
    }
  },
  "limits": []
}
```

## `brightness`

```json
{
  "id": "brightness",
  "aliases": [
    "lightness"
  ],
  "category": "color",
  "backend": "ffmpeg:eq",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "amount": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    }
  },
  "limits": []
}
```

## `chroma_key`

```json
{
  "id": "chroma_key",
  "aliases": [
    "chromakey",
    "green_screen"
  ],
  "category": "keying",
  "backend": "ffmpeg:colorkey",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "color": {
      "type": "color",
      "default": "0x00ff00"
    },
    "similarity": {
      "type": "number",
      "default": 0.1,
      "minimum": 1e-05,
      "maximum": 1.0
    },
    "blend": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 1.0
    }
  },
  "limits": [
    "native_RGB_distance_key_coverage_multiplies_input_alpha",
    "not_semantic_matting_or_despill",
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "similarity",
    "blend"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `color_balance`

```json
{
  "id": "color_balance",
  "aliases": [
    "colorbalance"
  ],
  "category": "color",
  "backend": "ffmpeg:colorbalance",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "red": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "green": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "blue": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    }
  },
  "limits": [
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "red",
    "green",
    "blue"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `color`

```json
{
  "id": "color",
  "aliases": [],
  "category": "color",
  "backend": "ffmpeg:eq",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "brightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "contrast": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 4.0
    },
    "saturation": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 4.0
    }
  },
  "limits": []
}
```

## `color_contrast`

```json
{
  "id": "color_contrast",
  "aliases": [
    "colorcontrast"
  ],
  "category": "color",
  "backend": "ffmpeg:colorcontrast",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "red": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "green": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "blue": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "red_weight": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "green_weight": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "blue_weight": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "preserve_luma": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 1.0
    }
  },
  "limits": [
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "red",
    "green",
    "blue",
    "red_weight",
    "green_weight",
    "blue_weight",
    "preserve_luma"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `color_levels`

```json
{
  "id": "color_levels",
  "aliases": [
    "levels",
    "colorlevels"
  ],
  "category": "color",
  "backend": "ffmpeg:colorlevels",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "input_black": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "input_white": {
      "type": "number",
      "default": 1.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "output_black": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "output_white": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "preserve": {
      "type": "enum",
      "default": "none",
      "description": "none, lum, max, avg, sum, nrm or pwr"
    }
  },
  "limits": [
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "input_black",
    "input_white",
    "output_black",
    "output_white"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `color_temperature`

```json
{
  "id": "color_temperature",
  "aliases": [
    "temperature",
    "warmth"
  ],
  "category": "color",
  "backend": "ffmpeg:colorbalance",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "kelvin": {
      "type": "number",
      "default": 6500.0,
      "minimum": 1000.0,
      "maximum": 40000.0
    }
  },
  "limits": [
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "kelvin"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `color_wheel`

```json
{
  "id": "color_wheel",
  "aliases": [
    "three_way_color",
    "three_way_wheel"
  ],
  "category": "color",
  "backend": "ffmpeg:colorbalance",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "shadows_red": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "shadows_green": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "shadows_blue": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "midtones_red": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "midtones_green": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "midtones_blue": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "highlights_red": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "highlights_green": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "highlights_blue": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "preserve_luma": {
      "type": "boolean",
      "default": false
    }
  },
  "limits": [
    "maps_to_ffmpeg_colorbalance_three_way_wheel",
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "shadows_red",
    "shadows_green",
    "shadows_blue",
    "midtones_red",
    "midtones_green",
    "midtones_blue",
    "highlights_red",
    "highlights_green",
    "highlights_blue"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `contrast`

```json
{
  "id": "contrast",
  "aliases": [],
  "category": "color",
  "backend": "ffmpeg:eq",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "amount": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 4.0
    }
  },
  "limits": []
}
```

## `curves`

```json
{
  "id": "curves",
  "aliases": [
    "curve"
  ],
  "category": "color",
  "backend": "ffmpeg:curves",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "all": {
      "type": "string",
      "default": "0/0 1/1",
      "description": "FFmpeg curves points, for example 0/0 0.5/0.4 1/1"
    },
    "master": {
      "type": "string",
      "default": "",
      "description": "Alias for the all/master curve"
    }
  },
  "limits": [
    "fixed_point_count_1_to_256",
    "six_decimal_8bit_x_bins_must_increase",
    "master_is_all_alias_not_post_master",
    "point_string_is_whitelist_validated"
  ],
  "keyframe_engine": "native-curve-points-cfr-v1",
  "keyframe_parameters": [
    "all.<index>.x",
    "all.<index>.y"
  ],
  "keyframe_point_index": {
    "minimum": 0,
    "maximum": 255,
    "topology": "static-point-count"
  },
  "keyframe_coordinate_range": [
    0,
    1
  ]
}
```

## `deband`

```json
{
  "id": "deband",
  "aliases": [
    "debanding"
  ],
  "category": "repair",
  "backend": "ffmpeg:deband",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "threshold": {
      "type": "number",
      "default": 0.02,
      "minimum": 0.001,
      "maximum": 0.5
    },
    "range": {
      "type": "integer",
      "default": 16,
      "minimum": 1,
      "maximum": 64
    }
  },
  "limits": []
}
```

## `deflicker`

```json
{
  "id": "deflicker",
  "aliases": [],
  "category": "repair",
  "backend": "ffmpeg:deflicker",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "size": {
      "type": "integer",
      "default": 5,
      "minimum": 2,
      "maximum": 129
    },
    "mode": {
      "type": "enum",
      "default": "am",
      "description": "am, gm, hm, qm, cm, pm or median"
    }
  },
  "limits": []
}
```

## `deshake`

```json
{
  "id": "deshake",
  "aliases": [
    "stabilize"
  ],
  "category": "repair",
  "backend": "ffmpeg:deshake",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "radius": {
      "type": "integer",
      "default": 16,
      "minimum": 1,
      "maximum": 128
    }
  },
  "limits": []
}
```

## `dctdnoiz`

```json
{
  "id": "dctdnoiz",
  "aliases": [],
  "category": "repair",
  "backend": "ffmpeg:dctdnoiz",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "sigma": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 999.0
    },
    "overlap": {
      "type": "integer",
      "default": -1,
      "minimum": -1,
      "maximum": 15
    },
    "block_bits": {
      "type": "integer",
      "default": 3,
      "minimum": 3,
      "maximum": 4,
      "description": "FFmpeg block size expressed as log2, 3=8px or 4=16px"
    }
  },
  "limits": []
}
```

## `draw_box`

```json
{
  "id": "draw_box",
  "aliases": [
    "drawbox",
    "rectangle"
  ],
  "category": "overlay",
  "backend": "ffmpeg:drawbox",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "x": {
      "type": "number",
      "default": 0.05,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "y": {
      "type": "number",
      "default": 0.05,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "width": {
      "type": "number",
      "default": 0.9,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "height": {
      "type": "number",
      "default": 0.9,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "color": {
      "type": "color",
      "default": "white@0.8"
    },
    "thickness": {
      "type": "integer",
      "default": 4,
      "minimum": 1,
      "maximum": 256
    }
  },
  "limits": []
}
```

## `edgedetect`

```json
{
  "id": "edgedetect",
  "aliases": [
    "edge",
    "edges"
  ],
  "category": "stylize",
  "backend": "ffmpeg:edgedetect",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "low": {
      "type": "number",
      "default": 0.1,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "high": {
      "type": "number",
      "default": 0.4,
      "minimum": 0.0,
      "maximum": 1.0
    }
  },
  "limits": []
}
```

## `exposure`

```json
{
  "id": "exposure",
  "aliases": [],
  "category": "color",
  "backend": "ffmpeg:exposure",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "amount": {
      "type": "number",
      "default": 0.0,
      "minimum": -3.0,
      "maximum": 3.0
    },
    "black": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    }
  },
  "limits": [
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "amount",
    "black"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `frame_interpolation`

```json
{
  "id": "frame_interpolation",
  "aliases": [
    "minterpolate",
    "optical_flow",
    "smooth_slow_motion",
    "slow_motion"
  ],
  "category": "motion",
  "backend": "ffmpeg:minterpolate",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "fps": {
      "type": "number",
      "default": 60.0,
      "minimum": 1.0,
      "maximum": 240.0,
      "description": "目标输出帧率"
    },
    "mi_mode": {
      "type": "enum",
      "default": "mci",
      "description": "dup、blend 或 mci"
    },
    "mc_mode": {
      "type": "enum",
      "default": "obmc",
      "description": "obmc 或 aobmc"
    },
    "me_mode": {
      "type": "enum",
      "default": "bilat",
      "description": "bidir 或 bilat"
    },
    "me": {
      "type": "enum",
      "default": "epzs",
      "description": "esa、tss、tdls、ntss、fss、ds、hexbs、epzs 或 umh"
    },
    "mb_size": {
      "type": "integer",
      "default": 16,
      "minimum": 4,
      "maximum": 16
    },
    "search_param": {
      "type": "integer",
      "default": 32,
      "minimum": 4,
      "maximum": 512
    },
    "vsbmc": {
      "type": "boolean",
      "default": false
    },
    "scd": {
      "type": "enum",
      "default": "fdiff",
      "description": "none 或 fdiff"
    },
    "scd_threshold": {
      "type": "number",
      "default": 10.0,
      "minimum": 0.0,
      "maximum": 100.0
    }
  },
  "limits": [
    "uses_local_ffmpeg_minterpolate",
    "motion_compensation_can_be_cpu_expensive",
    "scene_change_detection_is_filter_heuristic"
  ]
}
```

## `gamma`

```json
{
  "id": "gamma",
  "aliases": [
    "gamma_adjust"
  ],
  "category": "color",
  "backend": "ffmpeg:eq",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "amount": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.1,
      "maximum": 10.0
    }
  },
  "limits": []
}
```

## `gradfun`

```json
{
  "id": "gradfun",
  "aliases": [
    "gradient_smooth"
  ],
  "category": "repair",
  "backend": "ffmpeg:gradfun",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "threshold": {
      "type": "number",
      "default": 1.2,
      "minimum": 0.1,
      "maximum": 64.0
    },
    "radius": {
      "type": "integer",
      "default": 8,
      "minimum": 1,
      "maximum": 32
    }
  },
  "limits": []
}
```

## `grayscale`

```json
{
  "id": "grayscale",
  "aliases": [
    "black_white",
    "blackandwhite"
  ],
  "category": "stylize",
  "backend": "ffmpeg:hue",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {},
  "limits": []
}
```

## `hsl`

```json
{
  "id": "hsl",
  "aliases": [
    "hsl_adjust"
  ],
  "category": "color",
  "backend": "ffmpeg:hue",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -360.0,
      "maximum": 360.0,
      "description": "全局色相角度"
    },
    "saturation": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 4.0,
      "description": "全局饱和度倍率"
    },
    "lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0,
      "description": "映射到本地 FFmpeg hue brightness 的明度偏移"
    }
  },
  "limits": [
    "lightness_uses_ffmpeg_hue_brightness_mapping"
  ]
}
```

## `hqdn3d`

```json
{
  "id": "hqdn3d",
  "aliases": [],
  "category": "repair",
  "backend": "ffmpeg:hqdn3d",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "luma_spatial": {
      "type": "number",
      "default": 4.0,
      "minimum": 0.0,
      "maximum": 30.0
    },
    "chroma_spatial": {
      "type": "number",
      "default": 3.0,
      "minimum": 0.0,
      "maximum": 30.0
    },
    "luma_temporal": {
      "type": "number",
      "default": 6.0,
      "minimum": 0.0,
      "maximum": 30.0
    },
    "chroma_temporal": {
      "type": "number",
      "default": 4.5,
      "minimum": 0.0,
      "maximum": 30.0
    }
  },
  "limits": []
}
```

## `histeq`

```json
{
  "id": "histeq",
  "aliases": [
    "histogram_equalize"
  ],
  "category": "color",
  "backend": "ffmpeg:histeq",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {},
  "limits": []
}
```

## `hflip`

```json
{
  "id": "hflip",
  "aliases": [
    "flip",
    "horizontal_flip"
  ],
  "category": "transform",
  "backend": "ffmpeg:hflip",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {},
  "limits": []
}
```

## `hue`

```json
{
  "id": "hue",
  "aliases": [
    "hue_rotate"
  ],
  "category": "color",
  "backend": "ffmpeg:hue",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "degrees": {
      "type": "number",
      "default": 0.0,
      "minimum": -360.0,
      "maximum": 360.0
    }
  },
  "limits": []
}
```

## `invert`

```json
{
  "id": "invert",
  "aliases": [
    "negative",
    "negate"
  ],
  "category": "stylize",
  "backend": "ffmpeg:negate",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {},
  "limits": []
}
```

## `lens_correction`

```json
{
  "id": "lens_correction",
  "aliases": [
    "lenscorrection"
  ],
  "category": "distortion",
  "backend": "ffmpeg:lenscorrection",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "k1": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "k2": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "cx": {
      "type": "number",
      "default": 0.5,
      "minimum": 0.0,
      "maximum": 1.0
    },
    "cy": {
      "type": "number",
      "default": 0.5,
      "minimum": 0.0,
      "maximum": 1.0
    }
  },
  "limits": [
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "k1",
    "k2",
    "cx",
    "cy"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `lut3d`

```json
{
  "id": "lut3d",
  "aliases": [
    "lut",
    "cube",
    "look"
  ],
  "category": "color",
  "backend": "ffmpeg:lut3d+blend",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "path": {
      "type": "path",
      "default": ""
    },
    "lut_id": {
      "type": "string",
      "default": "",
      "description": "项目内 lut register 生成的稳定资源 ID"
    },
    "interpolation": {
      "type": "enum",
      "default": "tetrahedral",
      "description": "nearest, trilinear, tetrahedral, pyramid or prism"
    },
    "intensity": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "0..1 强度关键帧；动态为 8-bit 编码 RGB 像素混合并保持 alpha；静态部分强度为 CUBE 网格混合"
    }
  },
  "limits": [
    "path_or_registered_lut_id_must_be_project_local",
    "dynamic_mix_is_8bit_encoded_RGB_not_linear_light_or_HDR",
    "static_partial_strength_requires_complete_3D_cube",
    "numeric_channels_only_bool_and_enum_stay_static",
    "complete_author_clock_at_CFR_samples",
    "recursive_command_and_sampling_budgets"
  ],
  "keyframe_parameters": [
    "intensity"
  ],
  "keyframe_engine": "native-color-command-cfr-v1"
}
```

## `noise`

```json
{
  "id": "noise",
  "aliases": [
    "film_grain"
  ],
  "category": "stylize",
  "backend": "ffmpeg:noise",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "amount": {
      "type": "integer",
      "default": 8,
      "minimum": 1,
      "maximum": 100
    }
  },
  "limits": []
}
```

## `posterize`

```json
{
  "id": "posterize",
  "aliases": [
    "posterization"
  ],
  "category": "stylize",
  "backend": "ffmpeg:lutrgb",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "levels": {
      "type": "integer",
      "default": 8,
      "minimum": 2,
      "maximum": 256
    }
  },
  "limits": []
}
```

## `rgb_curves`

```json
{
  "id": "rgb_curves",
  "aliases": [
    "rgb_curve",
    "channel_curves"
  ],
  "category": "color",
  "backend": "ffmpeg:curves",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "all": {
      "type": "string",
      "default": "0/0 1/1",
      "description": "未独立声明的 RGB 通道继承该曲线；不是后置 master"
    },
    "red": {
      "type": "string",
      "default": "",
      "description": "红色通道曲线"
    },
    "green": {
      "type": "string",
      "default": "",
      "description": "绿色通道曲线"
    },
    "blue": {
      "type": "string",
      "default": "",
      "description": "蓝色通道曲线"
    }
  },
  "limits": [
    "fixed_point_count_1_to_256",
    "six_decimal_8bit_x_bins_must_increase",
    "animated_channel_forks_static_all_if_no_own_points",
    "each_channel_is_whitelist_validated"
  ],
  "keyframe_engine": "native-curve-points-cfr-v1",
  "keyframe_parameters": [
    "all.<index>.x",
    "all.<index>.y",
    "red.<index>.x",
    "red.<index>.y",
    "green.<index>.x",
    "green.<index>.y",
    "blue.<index>.x",
    "blue.<index>.y"
  ],
  "keyframe_point_index": {
    "minimum": 0,
    "maximum": 255,
    "topology": "static-point-count"
  },
  "keyframe_coordinate_range": [
    0,
    1
  ]
}
```

## `selective_hsl`

```json
{
  "id": "selective_hsl",
  "aliases": [
    "hsl_bands",
    "eight_band_hsl"
  ],
  "category": "color",
  "backend": "ffmpeg:frei0r",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "red_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "red_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "red_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "orange_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "orange_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "orange_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "yellow_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "yellow_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "yellow_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "green_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "green_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "green_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "cyan_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "cyan_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "cyan_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "blue_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "blue_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "blue_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "purple_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "purple_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "purple_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "magenta_hue": {
      "type": "number",
      "default": 0.0,
      "minimum": -180.0,
      "maximum": 180.0
    },
    "magenta_saturation": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "magenta_lightness": {
      "type": "number",
      "default": 0.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "intensity": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 1.0
    }
  },
  "limits": [
    "eight_fixed_hue_centers_with_circular_triangular_partition",
    "weights_use_original_hue_simultaneously",
    "encoded_RGB_8bit_HSL_not_linear_light_HDR_or_vendor_look_equivalence",
    "achromatic_pixels_and_input_alpha_unchanged",
    "64KiB_per_kernel_16MiB_recursive_expression_budget",
    "shared_recursive_instances_and_state_samples"
  ],
  "keyframe_parameters": [
    "red_hue",
    "red_saturation",
    "red_lightness",
    "orange_hue",
    "orange_saturation",
    "orange_lightness",
    "yellow_hue",
    "yellow_saturation",
    "yellow_lightness",
    "green_hue",
    "green_saturation",
    "green_lightness",
    "cyan_hue",
    "cyan_saturation",
    "cyan_lightness",
    "blue_hue",
    "blue_saturation",
    "blue_lightness",
    "purple_hue",
    "purple_saturation",
    "purple_lightness",
    "magenta_hue",
    "magenta_saturation",
    "magenta_lightness",
    "intensity"
  ],
  "keyframe_engine": "encoded-rgb-eight-band-hsl-v1",
  "fallback_backends": [
    "ffmpeg:geq"
  ],
  "backend_selection": "verified-native-auto",
  "implementation_license": "MIT (original C kernel)",
  "implementation_license_file": "NATIVE_HSL_LICENSE.txt"
}
```

## `sepia`

```json
{
  "id": "sepia",
  "aliases": [],
  "category": "stylize",
  "backend": "ffmpeg:colorchannelmixer",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {},
  "limits": []
}
```

## `sharpen`

```json
{
  "id": "sharpen",
  "aliases": [
    "unsharp"
  ],
  "category": "detail",
  "backend": "ffmpeg:unsharp",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "amount": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 10.0
    }
  },
  "limits": []
}
```

## `smartblur`

```json
{
  "id": "smartblur",
  "aliases": [],
  "category": "blur",
  "backend": "ffmpeg:smartblur",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "radius": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.1,
      "maximum": 5.0
    },
    "strength": {
      "type": "number",
      "default": 1.0,
      "minimum": -1.0,
      "maximum": 1.0
    },
    "threshold": {
      "type": "integer",
      "default": 0,
      "minimum": -30,
      "maximum": 30
    }
  },
  "limits": []
}
```

## `solarize`

```json
{
  "id": "solarize",
  "aliases": [],
  "category": "stylize",
  "backend": "ffmpeg:lutrgb",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "threshold": {
      "type": "integer",
      "default": 128,
      "minimum": 0,
      "maximum": 255
    }
  },
  "limits": []
}
```

## `saturation`

```json
{
  "id": "saturation",
  "aliases": [],
  "category": "color",
  "backend": "ffmpeg:eq",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "amount": {
      "type": "number",
      "default": 1.0,
      "minimum": 0.0,
      "maximum": 4.0
    }
  },
  "limits": []
}
```

## `tblend`

```json
{
  "id": "tblend",
  "aliases": [],
  "category": "temporal",
  "backend": "ffmpeg:tblend",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "mode": {
      "type": "enum",
      "default": "average",
      "description": "FFmpeg tblend blend mode"
    }
  },
  "limits": []
}
```

## `threshold`

```json
{
  "id": "threshold",
  "aliases": [],
  "category": "stylize",
  "backend": "ffmpeg:lutyuv",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "value": {
      "type": "integer",
      "default": 128,
      "minimum": 0,
      "maximum": 255
    }
  },
  "limits": []
}
```

## `tmix`

```json
{
  "id": "tmix",
  "aliases": [],
  "category": "temporal",
  "backend": "ffmpeg:tmix",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {
    "frames": {
      "type": "integer",
      "default": 3,
      "minimum": 2,
      "maximum": 128
    },
    "scale": {
      "type": "number",
      "default": 0.0,
      "minimum": 0.0,
      "maximum": 1000.0
    }
  },
  "limits": []
}
```

## `vflip`

```json
{
  "id": "vflip",
  "aliases": [
    "vertical_flip"
  ],
  "category": "transform",
  "backend": "ffmpeg:vflip",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": false,
  "parameters": {},
  "limits": []
}
```

## `vignette`

```json
{
  "id": "vignette",
  "aliases": [],
  "category": "stylize",
  "backend": "ffmpeg:vignette",
  "source": "ffmpeg-local",
  "license": "inherit-local-ffmpeg-build",
  "keyframable": true,
  "parameters": {
    "angle": {
      "type": "number",
      "default": 0.785398,
      "minimum": 0.0,
      "maximum": 3.141593
    }
  },
  "limits": []
}
```

## 12 套运镜的完整参数

```json
[
  {
    "id": "zoom_in",
    "aliases": [
      "push_in"
    ],
    "category": "scale",
    "description": "在片段区间内平滑放大画面。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.scale"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "相对缩放增量"
      }
    },
    "limits": []
  },
  {
    "id": "zoom_out",
    "aliases": [
      "pull_out"
    ],
    "category": "scale",
    "description": "从放大状态平滑回到原始缩放。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.scale"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "相对缩放增量"
      }
    },
    "limits": []
  },
  {
    "id": "pan_left",
    "aliases": [
      "slide_left"
    ],
    "category": "position",
    "description": "沿 X 轴从右向左平移。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.position.x"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "归一化位移范围"
      }
    },
    "limits": []
  },
  {
    "id": "pan_right",
    "aliases": [
      "slide_right"
    ],
    "category": "position",
    "description": "沿 X 轴从左向右平移。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.position.x"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "归一化位移范围"
      }
    },
    "limits": []
  },
  {
    "id": "pan_up",
    "aliases": [
      "slide_up"
    ],
    "category": "position",
    "description": "沿 Y 轴从下向上平移。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.position.y"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "归一化位移范围"
      }
    },
    "limits": []
  },
  {
    "id": "pan_down",
    "aliases": [
      "slide_down"
    ],
    "category": "position",
    "description": "沿 Y 轴从上向下平移。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.position.y"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "归一化位移范围"
      }
    },
    "limits": []
  },
  {
    "id": "ken_burns",
    "aliases": [
      "kenburns"
    ],
    "category": "compound",
    "description": "同时平移和缩放的照片式镜头运动。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.scale",
      "transform.position.x",
      "transform.position.y"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "缩放及位移强度"
      }
    },
    "limits": []
  },
  {
    "id": "rotate_in",
    "aliases": [
      "rotate_left"
    ],
    "category": "rotation",
    "description": "从指定角度平滑旋转回零度。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.rotation"
    ],
    "parameters": {
      "degrees": {
        "type": "number",
        "default": 8.0,
        "minimum": -360.0,
        "maximum": 360.0,
        "description": "起始旋转角度"
      }
    },
    "limits": []
  },
  {
    "id": "rotate_out",
    "aliases": [
      "rotate_right"
    ],
    "category": "rotation",
    "description": "从零度平滑旋转到指定角度。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.rotation"
    ],
    "parameters": {
      "degrees": {
        "type": "number",
        "default": 8.0,
        "minimum": -360.0,
        "maximum": 360.0,
        "description": "结束旋转角度"
      }
    },
    "limits": []
  },
  {
    "id": "fade_in",
    "aliases": [
      "opacity_in"
    ],
    "category": "opacity",
    "description": "在片段区间内从透明渐入。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.opacity"
    ],
    "parameters": {},
    "limits": [
      "opacity_is_composited_as_a_transform_keyframe"
    ]
  },
  {
    "id": "fade_out",
    "aliases": [
      "opacity_out"
    ],
    "category": "opacity",
    "description": "在片段区间内渐出到透明。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.opacity"
    ],
    "parameters": {},
    "limits": [
      "opacity_is_composited_as_a_transform_keyframe"
    ]
  },
  {
    "id": "shake",
    "aliases": [],
    "category": "position",
    "description": "生成交替位置点的轻微抖动。",
    "engine": "timeline-keyframes",
    "source": "local-catalog",
    "license": "project-code",
    "properties": [
      "transform.position.x"
    ],
    "parameters": {
      "amount": {
        "type": "number",
        "default": 0.15,
        "minimum": 0.0,
        "maximum": 1.0,
        "description": "抖动范围"
      },
      "points": {
        "type": "integer",
        "default": 8,
        "minimum": 2,
        "maximum": 64,
        "description": "关键帧点数"
      }
    },
    "limits": [
      "uses_deterministic_linear_keyframes"
    ]
  }
]
```

## Portable motion packs / 可复用运镜包

CLI 0.1.16 adds six parameterized paths and capture/reuse of existing curves, compiled into ordinary editable transform keys. The twelve base motion presets above remain unchanged. [Full parameter ranges, commands and actual six MP4/GIF previews](MOTION_PACKS.md) · [Installed/Skill evidence](../validation/可复用运镜包实测_2026-10-25.md). Generated paths are 65-point polylines; CPU composition and natural/subject-follow quality remain limited.
