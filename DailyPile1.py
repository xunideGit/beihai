import streamlit as st
import pandas as pd
import plotly.express as px

def main():
    # 设置页面标题
    st.title("每日桩基完成量")

    # 读取Excel文件中的Sheet1表单数据
    file_path = 'DailyPile.xlsx'  # 假设文件在同目录下
    sheet_name = 'Sheet1'  # 表单名称
    data = pd.read_excel(file_path, sheet_name=sheet_name, header=None)  # 指定header=None

    # 确保数据的列索引正确
    # 假设第0列是日期，第1列是完成量
    data.columns = ['日期', '完成量']  # 为数据添加表头
    dates = data['日期']  # 第0列是日期
    completion = data['完成量']  # 第1列是完成量

    # 创建交互式柱状图
    fig = px.bar(
        x=dates,
        y=completion,
        labels={'x': '日期', 'y': '完成量'},
        title='每日桩基完成量柱状图'
    )

    # 显示图表
    st.plotly_chart(fig)

    # 使用st.expander创建可折叠区域
    with st.expander("📈 数据明细"):
        # 显示数据表
        st.dataframe(
            data.style.format({
                '日期': lambda x: x.strftime('%Y-%m-%d'),  # 格式化日期
                '完成量': '{:.0f}'  # 格式化完成量为整数
            }).background_gradient(cmap='YlGnBu'),  # 添加背景渐变
            height=300
        )

    # 提供下载按钮
    st.download_button(
        "下载完整数据",
        data=data.to_csv(index=False, date_format='%Y-%m-%d').encode('utf-8-sig'),  # 格式化日期并编码
        file_name="daily_pile_data.csv",  # 下载文件名
        mime="text/csv"  # 文件类型
    )

if __name__ == "__main__":
    main()