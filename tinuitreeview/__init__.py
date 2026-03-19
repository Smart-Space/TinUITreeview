"""
TinUITreeView — 基于原 add_treeview 重构的面向对象树状列表控件
包含 TinUITreeItem（节点）和 TinUITreeView（控件）两个类

增删改操作：
  tree.add_node(text, parent=None)  - 添加节点（parent为None时添加到根）
  tree.remove_node(item)            - 删除节点及其所有子节点
  tree.rename_node(item, new_text)  - 重命名节点
  tree.get_selected()               - 获取当前选中的 TinUITreeItem
"""
import tkinter as tk
import tkinter.font as tkfont
from tinui import BasicTinUI
from tinui.TinUI import TinUIString


class TinUITreeItem:
    """
    代表树中的一个节点，持有画布对象 id 以及父/子关系。

    属性（只读，由 TinUITreeView 维护）：
        text      - 节点显示文本
        back      - 背景矩形画布 id（也是 items 字典的键）
        te        - 文字画布 id
        sign      - 展开/收起三角图标画布 id（叶节点为 None）
        parent    - 父 TinUITreeItem，根节点为 None
        children  - 子 TinUITreeItem 列表
    """

    def __init__(self, text: str, back, te, sign=None, parent=None):
        self.text: str = text
        self.back = back          # 背景
        self.te = te              # 文字
        self.sign = sign          # 折叠图标，叶节点为 None
        self.parent: TinUITreeItem|None = parent
        self.children: list[TinUITreeItem] = []

    def __repr__(self):
        return f"TinUITreeItem({self.text!r}, children={len(self.children)})"


tvlight = {
    'fg':'#1a1a1a','bg':'#f3f3f3',
    'onfg':'#1a1a1a','onbg':'#eaeaea',
    'oncolor':'#0067C0','signcolor':'#8a8a8a',
}
tvdark = {
    'fg':'#ffffff','bg':'#202020',
    'onfg':'#ffffff','onbg':'#2d2d2d',
    'oncolor':'#4CC2FF','signcolor':'#9f9f9f',
}

class TinUITreeView:
    _ICON_OPEN   = "\ue96e"
    _ICON_CLOSED = "\ue970"

    def __init__(
        self,
        master: BasicTinUI,
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
    ):
        self._master = master
        self._fg = fg
        self._bg = bg
        self._onfg = onfg
        self._onbg = onbg
        self._oncolor = oncolor
        self._signcolor = signcolor
        self._width = width
        self._height = height
        self._anchor = anchor
        self._command = command

        _font = tkfont.Font(font=font)
        self._font      = _font
        self._font_size = _font.cget("size")

        self._nowitem: TinUITreeItem|None = None # 当前选中节点
        self._roots: list[TinUITreeItem] = [] # 根节点列表
        # back_id->TinUITreeItem的全局查找表
        self._item_map: dict[object, TinUITreeItem] = {}

        self._box = BasicTinUI(master, bg=bg, width=width, height=height)
        self._cavui = master.create_window(
            pos, window=self._box, width=width, height=height, anchor="nw"
        )
        master.windows.append(self._box)
        self.uid = TinUIString(f"tinuitreeview-{self._cavui}")
        master.addtag_withtag(self.uid, self._cavui)

        self._hscroll = master.add_scrollbar(
            (pos[0] + width - 8, pos[1]),
            widget=self._box, height=height,
            bg=bg, color=signcolor, oncolor=signcolor,
        )[-1]
        self._vscroll = master.add_scrollbar(
            (pos[0], pos[1] + height - 8),
            widget=self._box, height=width,
            direction="x",
            bg=bg, color=signcolor, oncolor=signcolor,
        )[-1]
        master.addtag_withtag(self.uid, self._hscroll)
        master.addtag_withtag(self.uid, self._vscroll)

        self._box.add_back((0, 0, 0, 0), linew=0)

        self._load_content(content)

        # 选中指示线
        first_back = list(self._item_map.keys())[0] if self._item_map else None
        if first_back is not None:
            bbox = self._box.bbox(first_back)
            self._linew = bbox[3] - bbox[1]
        else:
            self._linew = 20
        self._line = self._box.create_line(
            (1, self._linew / 3, 1, self._linew * 2 / 3),
            fill=oncolor, width=3, capstyle="round",
        )
        self._box.moveto(self._line, 0, -self._linew - height)
        self._box.itemconfig(self._line, state="hidden")

        x1, y1, x2, y2 = master.bbox(self.uid)
        self._allback = master._BasicTinUI__ui_polygon(
            ((x1, y1), (x2, y2)), outline=bg, fill=bg, width=9, tags=self.uid
        )

        master.lift(self._cavui)
        master.lift(self._hscroll)
        master.lift(self._vscroll)
        self._checkscroll()

        dx, dy = master._BasicTinUI__auto_anchor(self.uid, pos, anchor)
        self._hscroll.move(dx, dy, height)
        self._vscroll.move(dx, dy, width)

        self._box.bind("<Destroy>", self._on_destroy)

        self.uid.layout = self._layout

    # ====================
    # 公开 API
    # ====================

    def get_selected(self) -> TinUITreeItem|None:
        """返回当前选中节点"""
        return self._nowitem

    def add_node(
        self,
        text: str,
        parent: TinUITreeItem|None = None,
    ) -> TinUITreeItem:
        """
        添加一个新节点。
          parent=None -> 追加到根级
          parent=item -> 作为 item 的子节点追加

        返回新建的 TinUITreeItem
        """
        padx = self._calc_padx(parent)
        item = self._create_leaf(text, padx, parent)

        if parent is None:
            self._roots.append(item)
        else:
            self._make_parent_expandable(parent)
            parent.children.append(item)
            self._update_items_dict(parent)

        self._fix_back_width(item.back)
        self._bind_events(item)
        self._checkscroll()
        return item

    def remove_node(self, item: TinUITreeItem):
        """
        删除节点及其所有后代
        若被删节点是父节点的最后一个子节点，同时移除父节点的折叠图标
        """
        # 收集所有需要删除的节点（包含后代）
        to_delete = self._collect_descendants(item)
        to_delete.insert(0, item)

        # 计算需要向上移动的高度
        bbox_list = [self._box.bbox(n.back) for n in to_delete if self._box.bbox(n.back) is not None]
        if bbox_list:
            total_h = sum(b[3] - b[1] + 3 for b in bbox_list)
            # 找到第一个被删节点在所有节点中的索引
            all_backs = list(self._item_map.keys())
            first_idx = all_backs.index(item.back) if item.back in all_backs else None
        else:
            total_h = 0
            first_idx = None

        # 从画布移除
        for node in to_delete:
            for cid in self._canvas_ids(node):
                self._box.delete(cid)
            del self._item_map[node.back]

        # 整体上移后续节点
        if first_idx is not None:
            remaining_backs = list(self._item_map.keys())
            # 找到删除后第一个需要上移的 back
            for _, back in enumerate(remaining_backs):
                node_item = self._item_map[back]
                # 仅移动位置在删除区域之后的节点
                b = self._box.bbox(back)
                if b and bbox_list and b[1] >= bbox_list[0][1]:
                    for cid in self._canvas_ids(node_item):
                        self._box.move(cid, 0, -total_h)

        # 修正父节点
        parent = item.parent
        if parent is not None:
            parent.children = [c for c in parent.children if c is not item]
            if not parent.children:
                # 父节点变为叶节点，移除折叠图标
                self._demote_to_leaf(parent)
            else:
                self._update_items_dict(parent)
        else:
            self._roots = [r for r in self._roots if r is not item]

        # 若删除的是选中节点，清除选中
        if self._nowitem in to_delete or self._nowitem is item:
            self._nowitem = None
            self._box.itemconfig(self._line, state="hidden")

        self._checkscroll()

    def rename_node(self, item: TinUITreeItem, new_text: str):
        """重命名节点"""
        item.text = new_text
        self._box.itemconfig(item.te, text=new_text)

    def close_all(self):
        """折叠所有可折叠节点"""
        for item in list(self._item_map.values()):
            if item.sign and self._box.itemcget(item.sign, "text") == self._ICON_OPEN:
                self._close_view(item)

    def open_all(self):
        """展开所有可折叠节点"""
        for item in list(self._item_map.values()):
            if item.sign and self._box.itemcget(item.sign, "text") == self._ICON_CLOSED:
                self._open_view(item)

    # ====================
    # 初始化加载
    # ====================

    def _load_content(self, content, parent: "TinUITreeItem | None" = None, padx=5):
        """递归解析原始 content 格式并构建节点树。"""
        children: list[TinUITreeItem] = []
        for text in content:
            if isinstance(text, str):
                item = self._create_leaf(text, padx, parent)
            else:
                # (label, (child1, child2, ...))
                item = self._create_branch(text[0], padx, parent)
                self._load_content(text[1], item, padx + 15)
                self._update_items_dict(item)
                # 默认折叠图标绑定
                self._box.tag_bind(
                    item.sign, "<Button-1>",
                    lambda _, n=item: self._close_view(n),
                )
            self._fix_back_width(item.back)
            self._bind_events(item)
            children.append(item)

        if parent is None:
            self._roots.extend(children)
        else:
            parent.children = children

    def _create_leaf(self, text: str, padx: int, parent) -> TinUITreeItem:
        y = self._endy() + 3
        te = self._box.create_text(
            (padx + 15, y), text=text,
            font=self._font, fill=self._fg, tags="item", anchor="nw",
        )
        back = self._box.add_back((), (te,), fg=self._bg, bg=self._bg, linew=0)
        item = TinUITreeItem(text, back, te, sign=None, parent=parent)
        self._item_map[back] = item
        return item

    def _create_branch(self, text: str, padx: int, parent) -> TinUITreeItem:
        y = self._endy() + 3
        sign = self._box.create_text(
            (padx - 1, y + 3), text=self._ICON_OPEN,
            font=f"{{Segoe Fluent Icons}} {self._font_size}",
            fill=self._signcolor, anchor="nw",
        )
        signx = self._box.bbox(sign)[2]
        te = self._box.create_text(
            (signx, y), text=text,
            font=self._font, fill=self._fg, tags="item", anchor="nw",
        )
        back = self._box.add_back((), (sign, te), fg=self._bg, bg=self._bg, linew=0)
        item = TinUITreeItem(text, back, te, sign=sign, parent=parent)
        self._item_map[back] = item
        return item

    # ====================
    # 内部展开 / 折叠
    # ====================

    def _open_view(self, item: TinUITreeItem):
        if self._box.itemcget(item.sign, "text") == self._ICON_OPEN:
            return
        self._box.itemconfig(item.sign, text=self._ICON_OPEN)
        self._box.tag_bind(
            item.sign, "<Button-1>", lambda _, n=item: self._close_view(n)
        )
        # 只展开直接子节点（子节点的子节点保持其折叠状态）
        move_tag = f"move{item.back}"
        for child in item.children:
            for cid in self._canvas_ids(child):
                self._box.addtag_withtag(move_tag, cid)
        self._box.itemconfig(move_tag, state="normal")
        bbox = self._box.bbox(move_tag)
        if bbox is None:
            self._box.dtag(move_tag)
            return
        last_leaf_back = self._get_last_back(item)
        index = list(self._item_map.keys()).index(last_leaf_back) + 1
        self._move_index(index, bbox[3] - bbox[1])
        self._box.dtag(move_tag)

        if self._nowitem is not None:
            self._click(self._nowitem)
        self._checkscroll()

    def _close_view(self, item: TinUITreeItem):
        if self._box.itemcget(item.sign, "text") == self._ICON_CLOSED:
            return
        self._box.itemconfig(item.sign, text=self._ICON_CLOSED)
        self._box.tag_bind(
            item.sign, "<Button-1>", lambda _, n=item: self._open_view(n)
        )
        desc = self._collect_descendants(item)
        move_tag = f"move{item.back}"
        for node in desc:
            for cid in self._canvas_ids(node):
                self._box.addtag_withtag(move_tag, cid)
            # 递归折叠
            if node.sign and self._box.itemcget(node.sign, "text") == self._ICON_OPEN:
                self._close_view(node)
        bbox = self._box.bbox(move_tag)
        if bbox is None:
            self._box.dtag(move_tag)
            return
        self._box.itemconfig(move_tag, state="hidden")
        last_desc_back = desc[-1].back if desc else item.back
        index = list(self._item_map.keys()).index(last_desc_back) + 1
        self._move_index(index, bbox[1] - bbox[3])
        self._box.dtag(move_tag)

        if self._nowitem in desc:
            self._box.itemconfig(self._line, state="hidden")
        elif self._nowitem is not None:
            self._click(self._nowitem)
        self._checkscroll()

    # ====================
    # 内部事件
    # ====================

    def _click(self, item: TinUITreeItem, send=False):
        if self._nowitem is not None:
            self._box.itemconfig(self._nowitem.back, fill=self._bg, outline=self._bg)
            self._box.itemconfig(self._nowitem.te, fill=self._fg)
        self._box.itemconfig(item.back, fill=self._onbg, outline=self._onbg)
        self._box.itemconfig(item.te, fill=self._onfg)
        self._nowitem = item
        posi = self._box.bbox(item.back)
        if posi is None:
            self._box.itemconfig(self._line, state="hidden")
            return
        self._box.itemconfig(self._line, state="normal")
        self._box.moveto(self._line, -1, posi[1] + self._linew / 5)
        if self._command is not None and send:
            path = []
            node = item
            while node is not None:
                path.append(node)
                node = node.parent
            self._command(path[::-1])

    def _bind_events(self, item: TinUITreeItem):
        targets = (item.back, item.te)
        for cid in targets:
            self._box.tag_bind(
                cid, "<Enter>",
                lambda _, n=item: self._buttonin(n),
            )
            self._box.tag_bind(
                cid, "<Leave>",
                lambda _, n=item: self._buttonout(n),
            )
            self._box.tag_bind(
                cid, "<Button-1>",
                lambda _, n=item: self._click(n, True),
            )

    def _buttonin(self, item: TinUITreeItem):
        if item is not self._nowitem:
            self._box.itemconfig(item.back, fill=self._onbg, outline=self._onbg)

    def _buttonout(self, item: TinUITreeItem):
        if item is not self._nowitem:
            self._box.itemconfig(item.back, fill=self._bg, outline=self._bg)

    # ====================
    # 内部结构辅助
    # ====================

    def _endy(self) -> int:
        bbox = self._box.bbox("all")
        return bbox[-1] if bbox else 0

    def _calc_padx(self, parent: TinUITreeItem|None) -> int:
        """根据父节点层级计算缩进量"""
        depth = 0
        node = parent
        while node is not None:
            depth += 1
            node = node.parent
        return 5 + depth * 15

    def _canvas_ids(self, item: TinUITreeItem):
        """返回节点关联的所有画布 id（背景、文字、图标）"""
        ids = [item.back, item.te]
        if item.sign is not None:
            ids.append(item.sign)
        return ids

    def _collect_descendants(self, item: TinUITreeItem) -> list:
        """BFS/DFS 收集所有后代节点（按树序）"""
        result = []
        stack = list(item.children)
        while stack:
            node = stack.pop(0)
            result.append(node)
            stack = list(node.children) + stack
        return result

    def _get_last_back(self, item: TinUITreeItem):
        """获取以 item 为根的子树中最后一个后代的 back id"""
        desc = self._collect_descendants(item)
        return desc[-1].back if desc else item.back

    def _move_index(self, index: int, dy: int):
        """将 item_map 中第 index 个之后的所有节点整体移动 dy"""
        all_backs = list(self._item_map.keys())
        for back in all_backs[index:]:
            node = self._item_map[back]
            for cid in self._canvas_ids(node):
                self._box.move(cid, 0, dy)

    def _fix_back_width(self, back):
        """调整背景矩形宽度以填满视口"""
        old_coords = self._box.coords(back)
        old_coords[0] = old_coords[6] = 6
        bbox = self._box.bbox(back)
        if bbox and bbox[2] - bbox[0] < self._width:
            old_coords[2] = old_coords[4] = self._width - 9
        self._box.coords(back, old_coords)

    def _update_items_dict(self, parent: TinUITreeItem):
        """在 parent.children 变化后同步（此处仅占位，结构已由 TinUITreeItem.children 维护）"""
        # 原代码用 items_dict 存储 back_id → child_back_ids
        # 重构后改为对象关系，此方法留作兼容扩展点
        pass

    def _make_parent_expandable(self, parent: TinUITreeItem):
        """若父节点原来是叶节点（无 sign），为其添加折叠图标。"""
        if parent.sign is not None:
            return  # 已有图标
        # 获取父节点文字的当前坐标
        te_coords = self._box.coords(parent.te)
        padx = self._calc_padx(parent.parent)  # 图标在文字左侧
        y = te_coords[1] + 3
        sign = self._box.create_text(
            (padx - 1, y), text=self._ICON_OPEN,
            font=f"{{Segoe Fluent Icons}} {self._font_size}",
            fill=self._signcolor, anchor="nw",
        )
        parent.sign = sign
        # 更新 back 关联的 items（将 sign 加入）
        self._box.addtag_withtag(parent.back, sign)
        self._box.tag_bind(
            sign, "<Button-1>", lambda _, n=parent: self._close_view(n)
        )

    def _demote_to_leaf(self, parent: TinUITreeItem):
        """将无子节点的父节点降级为叶节点"""
        if parent.sign is None:
            return
        self._box.delete(parent.sign)
        parent.sign = None

    # ====================
    # 内部滚动 / 布局
    # ====================

    def _checkscroll(self):
        bbox = self._box.bbox("all")
        if bbox is None:
            return
        if bbox[2] - bbox[0] <= self._width:
            self._master.itemconfig(self._cavui, height=self._height)
            self._master.itemconfig(self._vscroll, state="hidden")
        else:
            self._master.itemconfig(self._cavui, height=self._height - 8)
            self._master.itemconfig(self._vscroll, state="normal")
        if bbox[3] - bbox[1] <= self._height:
            self._master.itemconfig(self._cavui, width=self._width)
            self._master.itemconfig(self._hscroll, state="hidden")
        else:
            self._master.itemconfig(self._cavui, width=self._width - 8)
            self._master.itemconfig(self._hscroll, state="normal")
        self._box.config(scrollregion=bbox)

    def _repaintback(self):
        bbox = self._box.bbox("item")
        if bbox is None:
            return
        widgetwidth = max(self._width, bbox[2]) - 9
        for back in self._item_map:
            old_coords = self._box.coords(back)
            old_coords[2] = old_coords[4] = widgetwidth
            self._box.coords(back, old_coords)

    def _layout(self, x1, y1, x2, y2, expand=False):
        master = self._master
        if not expand:
            dx, dy = master._BasicTinUI__auto_layout(self.uid, (x1, y1, x2, y2), self._anchor)  # type: ignore
            self._hscroll.move(dx, dy, self._height)
            self._vscroll.move(dx, dy, self._width)
        else:
            dx, dy = master._BasicTinUI__auto_layout(self.uid, (x1, y1, x2, y2), "nw")  # type: ignore
            width2  = x2 - x1 - 9
            dw = width2 - self._width
            self._width = width2
            height2 = y2 - y1 - 9
            dh = height2 - self._height
            self._height = height2
            master.move(self._hscroll, dw, 0)
            self._hscroll.move(dx + dw, dy, self._height)
            master.move(self._vscroll, 0, dh)
            self._vscroll.move(dx, dy + dh, self._width)
            if self._allback is not None:
                coord = master.coords(self._allback)
                coord[2] = coord[4] = x2 - 4
                coord[5] = coord[7] = y2 - 4
                master.coords(self._allback, coord)
            master.itemconfig(self._cavui, width=self._width, height=self._height)
            self._repaintback()
            self._checkscroll()

    def _on_destroy(self, _):
        self._item_map.clear()
        self._roots.clear()
        self._nowitem = None


if __name__ == "__main__":
    from tinui import ExpandPanel
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