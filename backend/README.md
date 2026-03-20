### 代码结构

- app目录：后端代码

    - controllers目录：前端对接的接口的定义与实现
  
        - device_controller.py：物理设备相关的操作
        - record_controller.py：脚本录制回放相关的操作
        - mutate_controller.py：脚本扩增相关的操作

    - service目录：服务接口定义与实现

        - device_service.py：物理设备相关的操作
        - image_service.py：图像处理相关的操作
        - script_service.py：脚本录制回放相关的操作
        - mutation_service.py：脚本扩增相关的操作
        - implements目录：接口的具体实现
  
    - db目录：定义数据库连接和数据库操作

    - models目录：定义必要的数据结构

    - utils目录：java函数调用、控件提取，工具函数

    - create_tables.py：根据定义的schema创建数据库表
    
- main.py：fastapi应用主入口

- data目录：保存脚本录制所记录的相关数据，如屏幕截图、控件截图、layout文件等
```text
 ├─log 
 ├─screenshots 
 ├─scripts 
 ├─temp
  ├─ip
  ├─merge
  ├─ocr
  ├─draw
 ├─ui_xml
```

- main.py：后端启动的入口文件

### 运行环境

- `conda create -n guiaug python=3.10`
- `conda activate guiaug`
- `pip install -r requirements.txt`

- 运行create_tables.py，创建表

### 后端启动

- 连接设备，确保 `adb devices` 能够检测到设备
- 根目录下执行命令 `uvicorn app.main:app --reload` 或 `python main.py`