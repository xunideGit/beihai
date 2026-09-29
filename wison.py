import streamlit as st
import pandas as pd
import os
import time
from threading import Thread

# 设置页面标题
# st.set_page_config(page_title="Excel Data Display", layout="wide")

# 读取Excel文件
@st.cache_data  # 缓存数据以提高性能
def load_data(file_path, sheet_name=None):
    if sheet_name is not None:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
    else:
        df = pd.read_excel(file_path, engine='openpyxl')  # 修正拼写错误
    return df

def get_sheet_names(file_path):
    return pd.ExcelFile(file_path).sheet_names

# 图片轮播函数
def image_carousel(placeholder, valid_images):
    while True:
        for image_path in valid_images:
            with placeholder.container():
                st.image(image_path, caption=os.path.basename(image_path), use_container_width=True)
            time.sleep(3)  # 切换图片的时间间隔为3秒

# 主函数
def main():
    st.title("FCC项目-Wison合同数据（工期：202411-202710）")
    
    try:
        # 图片路径
        image_paths = ["合同数据.png", "开票情况.png"]
        
        # 检查图片是否存在
        valid_images = [path for path in image_paths if os.path.exists(path)]
        
        if len(valid_images) == 0:
            st.warning("没有找到有效的图片文件，请确保 合同数据.png 或 开票情况.png 存在于当前目录中。")
        else:
            enable_carousel = st.checkbox("启用图片", value=True)
            
            if enable_carousel:
                placeholder = st.empty()
                carousel_thread = Thread(target=image_carousel, args=(placeholder, valid_images))
                carousel_thread.daemon = True
                carousel_thread.start()
            else:
                for image_path in valid_images:
                    st.image(image_path, caption=os.path.basename(image_path), use_container_width=True)
        
        file_path = "wison.xlsx"
        sheet_names = get_sheet_names(file_path)
        selected_sheet = st.selectbox("选择工作表:", sheet_names)
        df = load_data(file_path, selected_sheet)
        
        # 不再移除后缀，允许列名唯一性
        # df.columns = df.columns.str.replace(r'\.\d+$', '', regex=True)
        
        st.write("### 数据预览")
        st.dataframe(df)

    except FileNotFoundError:
        st.error("文件未找到，请确保 wison.xlsx 文件和所有图片文件存在于当前目录中。")
    except Exception as e:
        st.error(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()
