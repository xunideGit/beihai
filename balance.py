import pandas as pd
import streamlit as st


def main():
    st.title("FCC项目银行余额")
    try:
        # 读取 Excel 文件的第一个表单
        df = pd.read_excel('balance.xlsx', sheet_name=0)
        # 在 Streamlit 中展示表格
        st.dataframe(df)
    except FileNotFoundError:
        st.error("未找到 'balance.xlsx' 文件，请检查文件路径和文件名。")
    except Exception as e:
        st.error(f"发生未知错误: {e}")

    
