I want to build a mini but useful tool project that easy to collect the comment and danmu(only bilibili without douyin) from video platforms.

this tool is plug in style, and easy to use. it supports use with a built-in UI independently or copy the skill built in this project or just copy the core py files inside skill directory to their own projects.

in another words, the project structure is:
{[(core py files) wrapped skill structure] additional UI}
APIs recorded in core py files, usages and notes recorded in skill structure, additional UI call the APIs in core files and follow the usages and notes in skill structure.

for multiple platform support, the project structure is:
{[(bilibili core py files, douyin core py files) bilibili clawer skill, douyin clawer skill] unified UI with switchable tabs}
now only support bilibili is enough. you need design an unified and standard skill directory structure to enable the future expansion for the unified UI.

core files only record the main APIs, md files in skill only record recommended abstract strategies(such as rate-limiting), and the outermost UI implement these strategies.

the responsibilities of UI is simple for facing beginner users, choose a platform, input the bv link(bilibili) and required certification information(give the one-click-copy command to allow user easy to get these information on browser console), check the fields user needed, then start grab(show the progress bar and related logs), finally store the results. that is all. all optimizations and detailed strategies hide behind the UI program.

README.md supports and zh-CN and en-US.
write code annotation and skill description in fully English.

for actual bilibili grab ways, you can refer to D:\development-projects\study-projects\blblcd and D:\development-projects\study-projects\bilicmtcrawl