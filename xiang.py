import streamlit as st
import pandas as pd
import plotly.express as px

def main():
    st.title("FCC项目-2025May用款计划")
    try:
        # 读取 Excel 文件
        df = pd.read_excel('xiang.xlsx')

        # 提取四个象限的数据（修改行范围为完整数据）
        important_urgent = df.iloc[4:19, 0:6]  # 从第5行开始直到末尾
        urgent_unimportant = df.iloc[4:19, 6:12]
        important_not_urgent = df.iloc[21:32, 0:6]
        unimportant_not_urgent = df.iloc[21:32, 6:12]

        # 设置列名（保持不变）
        columns = ['序号', '事件', '部门', '截止日期', '倒计时（天）', '状态']
        important_urgent.columns = columns
        urgent_unimportant.columns = columns
        important_not_urgent.columns = columns
        unimportant_not_urgent.columns = columns

        # 添加象限列（保持不变）
        important_urgent['紧急程度'] = '重要且紧急'
        urgent_unimportant['紧急程度'] = '紧急不重要'
        important_not_urgent['紧急程度'] = '重要不紧急'
        unimportant_not_urgent['紧急程度'] = '不重要不紧急'

        # 合并数据（保持不变）
        combined_df = pd.concat([important_urgent, urgent_unimportant,
                                 important_not_urgent, unimportant_not_urgent])

        # 过滤空行（保持不变）
        combined_df = combined_df.dropna(how='all')

        # 创建一个新的列用于组合部门和事件
        combined_df['部门_事件'] = combined_df['部门'] + '_' + combined_df['事件']

        # 添加部门筛选器
        all_departments = ['全部'] + combined_df['部门'].unique().tolist()
        selected_department = st.selectbox("选择部门", all_departments)

        if selected_department != '全部':
            filtered_df = combined_df[combined_df['部门'] == selected_department]
        else:
            filtered_df = combined_df

        # （其余代码保持不变）
        hover_template = "<b>事件</b>: %{customdata[0]}<br>" + \
                         "<b>部门</b>: %{customdata[1]}<br>" + \
                         "<b>截止日期</b>: %{customdata[2]}<br>" + \
                         "<b>倒计时（天）</b>: %{y}<br>" + \
                         "<b>状态</b>: %{customdata[3]}<br>" + \
                         "<b>紧急程度</b>: %{x}<br>" + \
                         "<extra></extra>"

        fig = px.bar(filtered_df, x='紧急程度', y='倒计时（天）', color='部门_事件',
                     custom_data=['事件', '部门', '截止日期', '状态'],
                     barmode='stack')
        fig.update_traces(hovertemplate=hover_template)

        # 显示图表和明细（保持不变）
        st.plotly_chart(fig)

        with st.expander("数据明细", expanded=False):
            st.markdown("""
                <style>
                .stDataFrame td {
                    white-space: nowrap;
                }
                </style>
            """, unsafe_allow_html=True)
            st.dataframe(filtered_df)

            csv = filtered_df.to_csv(sep='\t', na_rep='nan')
            st.download_button(
                label="下载数据明细",
                data=csv,
                file_name='data_details.csv',
                mime='text/csv'
            )

    except FileNotFoundError:
        st.error("未找到 'xiang.xlsx' 文件，请确保文件存在。")
    except Exception as e:
        st.error(f"发生未知错误: {e}")

if __name__ == "__main__":
    main()
    
