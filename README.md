# TinUITreeview

[TinUI](https://github.com/Smart-Space/TinUI)的高级树状图控件。相比于TinUI原生`treeview`，给拓展提供对树状图的增删改功能，以及更细化的操作实现。

---

# 使用

## TinUITreeItem

树状图元素，用来表示树中的一个节点。这是一个抽象元素，包含如下信息：

- text - 节点显示文本
- back - 背景矩形画布 id（也是 items 字典的键）
- te - 文字画布 id
- sign - 展开/收起三角图标画布 id（叶节点为 None）
- parent - 父 TinUITreeItem，根节点为 None
- children  - 子 TinUITreeItem 列表

不过，使用者并不需要在意这些细节，只需要知道这是节点元素即可。以上信息可作为属性直接获取。

## TinUITreeView

```python
TinUITreeView(
    master:BasicTinUI,
    pos: tuple,
    fg="#1a1a1a",
    bg="#f3f3f3",
    onfg="#1a1a1a",
    onbg="#eaeaea",
    oncolor="#3041d8",
    signcolor="#8a8a8a",
    width=200,
    height=300,
    font="微软雅黑 12",
    content=(
        ("one", ("1", "2", "3")),
        "two",
        ("three", ("a", ("b", ("b1", "b2", "b3")), "c")),
        "four",
    ),
    anchor="nw",
    command=None,
)
```

参数与TinUI原生`treeview`一致。

> [!NOTE]
>
> 另外，`tinuitreeview`提供`tvlight`和`tvdark`两种**样式配色**。

> [!tip]
>
> 通过`TinUITreeView.uid`获取控件标识符，用于TinUI面板布局。其对面板布局的响应与原生`treeview`一致。

#### get_selected()

返回选中的`TinUITreeItem`。

#### add_node(text:str, parent:TinUITreeItem=None)

添加节点。

- parent=None -> 追加到根级
- parent=item -> 作为 item 的子节点追加

返回新建的`TinUITreeItem`。

#### remove_node(item:TinUITreeItem)

删除节点及其后代。如果被删除点为亲节点最后一个节点，则亲节点变为叶子节点。

#### rename_node(item:TinUITreeItem, new_text:str)

重命名节点。

#### closs_all() / open_all()

同原生`treeview`。

---

# 示例

```python
# 导入必要模块...

def test(path):
    print("选中路径:", " > ".join(n.text for n in path))

root = tk.Tk()
tinui = BasicTinUI(root)
tinui.pack(fill='both',expand=True)
tree = TinUITreeView(tinui, (50, 50), command=test)

# 增
new_item = tree.add_node("新节点") # 添加到根
child = tree.add_node("子节点", parent=new_item)  # 添加到指定节点下

# 删
# tree.remove_node(child) # 同时删除所有后代，父节点若变为空则自动降级为叶节点

# 改
tree.rename_node(new_item, "renamed")

# 查
# selected = tree.get_selected() # 返回 TinUITreeItem 或 None
# print("当前选中:", selected)

# 展开/折叠
tree.close_all()
root.after(2000, tree.open_all) # 2秒后展开所有节点

rp = ExpandPanel(tinui, tree.uid)
def on_resize(e):
    rp.update_layout(5, 5, e.width-5, e.height-5)
tinui.bind("<Configure>", on_resize)

root.mainloop()
```

