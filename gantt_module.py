import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import colorsys
import os


# 初始化数据存储
def load_data():
    try:
        tasks = pd.read_csv('tasks.csv')

        # 强制转换日期列（带错误处理和日志）
        date_errors = []

        def safe_date_convert(col, series):
            try:
                return pd.to_datetime(series, format='%Y-%m-%d', errors='coerce')
            except Exception as e:
                date_errors.append(f"{col}列转换错误：{str(e)}")
                return pd.NaT

        tasks['Start'] = safe_date_convert('Start', tasks['Start'])
        tasks['End'] = safe_date_convert('End', tasks['End'])

        # 记录并显示转换错误
        if date_errors:
            st.error("日期数据异常：\n" + "\n".join(date_errors))

        # 过滤无效数据
        valid_tasks = tasks.dropna(subset=['Start', 'End']).copy()
        return valid_tasks

    except FileNotFoundError:
        return pd.DataFrame(columns=['Task', 'Category', 'Start', 'End', 'Progress', 'Status'])


def save_data(df):
    # 确保备份目录存在
    backup_dir = 'backup'
    os.makedirs(backup_dir, exist_ok=True)  # 关键修复

    # 创建数据备份
    backup_path = os.path.join(backup_dir, f"tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    df.to_csv(backup_path, index=False)

    # 验证数据完整性（原有代码不变）
    validation = {
        'date_format': df[['Start', 'End']].applymap(
            lambda x: isinstance(x, pd.Timestamp))
    }

    if not validation['date_format'].all().all():
        invalid_records = df[~validation['date_format'].all(axis=1)]
        st.error(f"发现{len(invalid_records)}条无效日期记录，已保留备份在{backup_path}")
        return

    # 保存主数据（原有代码不变）
    df.to_csv('tasks.csv', index=False)
    st.success(f"数据已保存！备份位置：{backup_path}")


def gantt_main():
    # 页面配置
    # st.set_page_config(page_title="FCC项目任务管理系统", layout="wide")

    # 初始化Session State
    if 'tasks' not in st.session_state:
        st.session_state.tasks = load_data()

    # 侧边栏 - 任务管理
    with st.sidebar:
        st.header("任务管理")

        with st.expander("📝 添加/修改任务"):
            operation = st.radio("操作类型", ["新建任务", "修改任务"], horizontal=True)

            if operation == "修改任务":
                existing_tasks = st.session_state.tasks['Task'].tolist()
                selected_task = st.selectbox("选择任务", existing_tasks)
                task_data = st.session_state.tasks[st.session_state.tasks['Task'] == selected_task].iloc[0]
            else:
                task_data = None

            with st.form("task_form"):
                # 使用显式的 is not None 判断
                default_category = task_data['Category'] if task_data is not None else ""
                category = st.text_input("任务分类", value=default_category)

                default_task = task_data['Task'] if task_data is not None else ""
                task_name = st.text_input("任务名称", value=default_task)

                # 处理日期字段
                if task_data is not None:
                    default_start = task_data['Start'].date()
                    default_end = task_data['End'].date()
                else:
                    default_start = datetime.today().date()
                    default_end = (datetime.today() + timedelta(days=7)).date()

                start_date = st.date_input("开始日期", value=default_start)
                end_date = st.date_input("结束日期", value=default_end)

                # 处理进度条
                default_progress = task_data['Progress'] if task_data is not None else 0
                progress = st.slider("进度 (%)", 0, 100, value=default_progress)

                # 处理状态选择器
                if task_data is not None:
                    status_index = 2 if task_data['Status'] == "已完成" else 1 if task_data['Status'] == "进行中" else 0
                else:
                    status_index = 0
                status = st.selectbox("状态", ["未开始", "进行中", "已完成"], index=status_index)

                submitted = st.form_submit_button("💾 保存")

                if submitted:
                    new_task = pd.DataFrame([[
                        task_name,
                        category,
                        pd.to_datetime(start_date),  # 显式转换
                        pd.to_datetime(end_date),  # 显式转换
                        progress,
                        status
                    ]], columns=st.session_state.tasks.columns)

                    if operation == "修改任务":
                        st.session_state.tasks = st.session_state.tasks[st.session_state.tasks['Task'] != selected_task]

                    st.session_state.tasks = pd.concat([st.session_state.tasks, new_task], ignore_index=True)
                    save_data(st.session_state.tasks)
                    st.success("任务已保存！")
                    st.rerun()

        with st.expander("🗑️ 删除任务"):
            task_to_delete = st.selectbox("选择要删除的任务", st.session_state.tasks['Task'].unique())
            if st.button("确认删除"):
                st.session_state.tasks = st.session_state.tasks[st.session_state.tasks['Task'] != task_to_delete]
                save_data(st.session_state.tasks)
                st.success("任务已删除！")
                st.rerun()

    # 筛选条件
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        categories = st.multiselect(
            "任务分类",
            options=st.session_state.tasks['Category'].unique(),
            default=st.session_state.tasks['Category'].unique()
        )

    # 修改时间范围选择部分
    with col2:
        time_range = st.selectbox(
            "时间范围",
            options=["all", "1w", "1m", "6m", "ytd", "1y"],
            index=0,
            format_func=lambda x: {
                "all": "全部",
                "1w": "最近1周",
                "1m": "最近1个月",
                "6m": "最近6个月",
                "ytd": "本年累计",
                "1y": "最近1年"
            }[x]
        )

    with col3:
        status_filter = st.multiselect(
            "任务状态",
            options=["未开始", "进行中", "已完成"],
            default=["未开始", "进行中", "已完成"]
        )

    # 时间范围过滤逻辑重构
    today = pd.Timestamp(datetime.today().date())
    date_ranges = {
        "all": (pd.Timestamp.min, pd.Timestamp.max),
        "1w": (today - pd.DateOffset(weeks=1), today),
        "1m": (today - pd.DateOffset(months=1), today),
        "6m": (today - pd.DateOffset(months=6), today),
        "ytd": (pd.Timestamp(today.year, 1, 1), today),
        "1y": (today - pd.DateOffset(years=1), today)
    }

    start_date, end_date = date_ranges[time_range]

    # 精确过滤逻辑
    filtered_tasks = st.session_state.tasks[
        (st.session_state.tasks['Category'].isin(categories)) &
        (st.session_state.tasks['Status'].isin(status_filter)) &
        (st.session_state.tasks['Start'] <= end_date) &
        (st.session_state.tasks['End'] >= start_date)
    ]

    # 统计指标
    total_tasks = len(filtered_tasks)
    avg_progress = filtered_tasks['Progress'].mean() if not filtered_tasks.empty else 0
    completed_tasks = len(filtered_tasks[filtered_tasks['Status'] == "已完成"])

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("总任务数", total_tasks)
    metric_col2.metric("平均进度", f"{avg_progress:.1f}%")
    metric_col3.metric("已完成任务", completed_tasks)
    metric_col4.metric("进行中任务", len(filtered_tasks[filtered_tasks['Status'] == "进行中"]))

    # 进度条数据处理
    progress_data = []
    for _, task in filtered_tasks.iterrows():
        progress_data.append({
            "Task": task["Task"],
            "Start": task["Start"],
            "Finish": task["Start"] + (task["End"] - task["Start"]) * task["Progress"] / 100,
            "Resource": task["Category"]
            # "Progress": task["Progress"]  # 添加进度信息
        })
    progress_df = pd.DataFrame(progress_data)

    # 甘特图
    # 替换原有甘特图生成代码
    if not filtered_tasks.empty:
        # 准备数据
        gantt_df = filtered_tasks.copy().rename(columns={'End': 'Finish'})
        gantt_df['Task'] = gantt_df['Task'] + " (" + gantt_df['Status'] + ")"

        # 生成RGB颜色（修改核心部分）
        def generate_colors(n):
            import colorsys
            HSV = [(x / n, 0.8, 0.9) for x in range(n)]
            RGB = list(map(lambda c: colorsys.hsv_to_rgb(*c), HSV))
            return [f'rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})' for r, g, b in RGB]

        categories = gantt_df['Category'].unique()
        colors = dict(zip(categories, generate_colors(len(categories))))

        # 创建基础甘特图（灰色背景）
        fig = ff.create_gantt(
            gantt_df,
            colors=['rgba(200, 200, 200, 0.3)'] * len(gantt_df),  # 半透明灰色
            bar_width=0.4
        )

        # 隐藏基础甘特图的悬停文本
        fig.update_traces(hoverinfo='skip')

        # 创建进度条（彩色部分）
        progress_fig = ff.create_gantt(
            progress_df,
            colors=[colors.get(res, '#CCCCCC') for res in progress_df['Resource']],  # 实色
            bar_width=0.35  # 略窄于背景条
        )

        # 隐藏进度条甘特图的悬停文本
        progress_fig.update_traces(hoverinfo='skip')

        # 合并图表
        fig.add_traces(progress_fig.data)

        # 添加当前日期指示线
        fig.add_vline(
            x=today.timestamp() * 1000,
            line_dash="dash",
            line_color="red",
            annotation_text="今日",
            annotation_position="top"
        )

        # 时间范围显示控制（关键修改部分）
        if time_range != "all":
            fig.update_xaxes(
                range=[start_date - pd.DateOffset(days=3),
                       end_date + pd.DateOffset(days=3)],
                rangeselector=None
            )
        else:
            # 去掉时间选择按钮
            fig.update_xaxes(rangeselector=None)

        # 统一布局配置
        fig.update_layout(
            height=600,
            title_text="任务甘特图",
            xaxis_title="时间轴",
            yaxis_title="任务",
            hovermode="y unified"
        )

        # 显示图表
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ 当前筛选条件下没有任务")

    # 修改数据表格部分（约196行附近）
    # 修改数据表格部分为以下代码
    with st.expander("📋 任务数据表"):
        # 安全创建可编辑副本
        editable_df = filtered_tasks.sort_values(by='Start').copy()

        # 定义安全的日期格式化函数
        def safe_date_format(series):
            try:
                return series.dt.strftime('%Y-%m-%d') if series.dtype == 'datetime64[ns]' else series.astype(str)
            except AttributeError:
                return series.astype(str)

        # 应用安全格式化
        editable_df['Start'] = safe_date_format(editable_df['Start'])
        editable_df['End'] = safe_date_format(editable_df['End'])

        # 配置文本列（带格式验证）
        column_config = {
            "Start": st.column_config.TextColumn(
                "开始时间",
                help="必须为YYYY-MM-DD格式",
                validate="^\\d{4}-\\d{2}-\\d{2}$",
                default="2023-01-01"
            ),
            "End": st.column_config.TextColumn(
                "结束时间",
                help="必须为YYYY-MM-DD格式",
                validate="^\\d{4}-\\d{2}-\\d{2}$",
                default="2023-12-31"
            ),
            "Progress": st.column_config.ProgressColumn(
                "进度",
                format="%.0f%%",
                min_value=0,
                max_value=100
            )
        }

        # 显示编辑器
        edited_df = st.data_editor(
            editable_df,
            use_container_width=True,
            column_config=column_config,
            key="data_editor"
        )

        # 转换并验证日期（带详细错误处理）
        date_conversion_errors = []
        try:
            edited_df['Start'] = pd.to_datetime(edited_df['Start'], format='%Y-%m-%d', errors='raise')
            edited_df['End'] = pd.to_datetime(edited_df['End'], format='%Y-%m-%d', errors='raise')
        except ValueError as e:
            bad_dates = edited_df[
                (~edited_df['Start'].apply(lambda x: isinstance(x, pd.Timestamp))) |
                (~edited_df['End'].apply(lambda x: isinstance(x, pd.Timestamp)))
            ]
            st.error(f"发现{len(bad_dates)}条无效日期记录：\n{bad_dates[['Task', 'Start', 'End']]}")
            st.stop()

        # 更新数据（带版本控制）
        if not edited_df.equals(filtered_tasks):
            # 更新主数据
            for index, row in edited_df.iterrows():
                task_name = row['Task']
                st.session_state.tasks.loc[st.session_state.tasks['Task'] == task_name] = row

            save_data(st.session_state.tasks)
            st.success("数据已更新！")
            st.rerun()

    # 数据下载
    csv = filtered_tasks.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 下载数据 (CSV)",
        data=csv,
        file_name='tasks.csv',
        mime='text/csv',
    )

    # 样式调整
    st.markdown("""
    <style>
    div[data-testid="stExpander"] details summary p {
        font-size: 1.2rem;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    gantt_main()