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
from typing import List
import weakref
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
        self.parent: weakref.ref[TinUITreeItem]|None = weakref.ref(parent) if parent else None
        self.children: list[TinUITreeItem] = []

        self.checkable = False  # 是否可选中，直接影响子节点的可选状态
        self.check_state = 0  # 选中状态：0=未选，1=全选，2=半选
        self.checkitems = (None,None,None)  # 可选状态图标的画布 id (outline, fill, text)

        self.icon: str|tk.PhotoImage|None = None  # 可选图标，Segoe Fluent Icons 字体的字符，或 PhotoImage 对象

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

    _ICON_CHECKOUTL = "\ue739"
    _ICON_CHECKFILL = "\ue73b"
    _ICON_CHECKHALF = "\uE73C"
    _ICON_CHECKTICK = "\ue73e"

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
        self.scale_value = master.scale_value

        _font = tkfont.Font(font=font)
        self._font      = _font
        self._font_size = _font.cget("size")
        self._icon_font = f"{{Segoe Fluent Icons}} {self._font_size}"
        self._icon_width = self._font.measure(self._ICON_OPEN)

        self._nowitem: TinUITreeItem|None = None # 当前选中节点
        self._roots: list[TinUITreeItem] = [] # 根节点列表
        # back_id->TinUITreeItem的全局查找表
        self._item_map: dict[object, TinUITreeItem] = {}
        self._order_list: list[object] = [] # back_id的有序列表，用于计算插入位置

        self._box = BasicTinUI(master, bg=bg, width=width, height=height)
        self._box.set_scale(self._master.TINUISCALE)
        self._cavui = master.create_window(
            pos, window=self._box, width=width, height=height, anchor="nw"
        )
        master.windows.append(self._box)
        self.uid = TinUIString(f"tinuitreeview-{self._cavui}")
        master.addtag_withtag(self.uid, self._cavui)

        self._hscroll = master.add_scrollbar(
            (pos[0] + width - self.scale_value(8), pos[1]),
            widget=self._box, height=height,
            bg=bg, color=signcolor, oncolor=signcolor,
        )[-1]
        self._vscroll = master.add_scrollbar(
            (pos[0], pos[1] + height - self.scale_value(8)),
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
            self._linew = self.scale_value(20)
        self._line = self._box.create_line(
            (self.scale_value(1), self._linew / 3, self.scale_value(1), self._linew * 2 / 3),
            fill=oncolor, width=self.scale_value(3,True), capstyle="round",
        )
        self._box.moveto(self._line, 0, -self._linew - height)
        self._box.itemconfig(self._line, state="hidden")

        x1, y1, x2, y2 = master.bbox(self.uid)
        self._allback = master._BasicTinUI__ui_polygon(
            ((x1, y1), (x2, y2)), outline=bg, fill=bg, width=self._master.TINUI_RADIUS_SMALL, tags=self.uid
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

    def select_node(self, values:List[str]) -> bool:
        """根据路径选择节点，路径格式为 [root_text, child_text, ...]"""
        current_level = self._roots
        selected_item = None
        for value in values:
            for item in current_level:
                if item.text == value:
                    selected_item = item
                    current_level = item.children
                    if item.sign: # 自动展开父节点以显示子节点
                        self._open_view(item)
                    break
            else:
                return False # 未找到匹配项，退出
        self._click(selected_item, send=True)
        y = self._box.coords(selected_item.back)[1] # 获取目标节点的 y 坐标用于居中显示
        self._box.yview_moveto(max(0, y - self._height / 2) / self._endy())
        return True

    def add_node(
        self,
        text: str,
        parent: TinUITreeItem|None = None,
        checkable: bool = False,
        check_state: bool = False,
    ) -> TinUITreeItem:
        """
        添加一个新节点。
          parent=None -> 追加到根级（画布末尾）
          parent=item -> 作为 item 的子节点追加，插入到该父节点子树末尾的正下方

        返回新建的 TinUITreeItem
        """
        padx = self._calc_padx(parent)

        if parent is None:
            # 根级：直接追加到画布末尾，insert_after=None
            item = self._create_leaf(text, padx, parent, checkable, check_state, insert_after=None)
            self._roots.append(item)
        else:
            if parent.checkable:
                checkable = True
                check_state = parent.check_state == 1
            # 找到父节点子树中最后一个节点，新节点插入其正下方
            last_node = self._get_last_node(parent)
            item = self._create_leaf(text, padx, parent, checkable, check_state, insert_after=last_node)
            self._make_parent_expandable(parent)
            parent.children.append(item)

        self._fix_back_width(item.back)
        self._bind_events(item)
        self._checkscroll()
        return item

    def remove_node(self, item: TinUITreeItem):
        """
        删除节点及其所有后代
        若被删节点是父节点的最后一个子节点，同时移除父节点的折叠图标
        """
        to_delete = self._collect_descendants(item)
        to_delete.insert(0, item)

        # 记录删除前在 _order_list 中的起始索引
        first_idx = self._order_list.index(item.back) if item.back in self._order_list else None

        # 计算被删节点占用的总高度（仅统计可见节点）
        total_h = 0
        for node in to_delete:
            bbox = self._box.bbox(node.back)
            if bbox is not None:
                total_h += bbox[3] - bbox[1] - 1
            for cid in self._canvas_ids(node):
                self._box.delete(cid)
            self._item_map.pop(node.back, None)
            self._order_list.remove(node.back)

        # 将被删区域之后的节点整体上移
        # total_h -= 4 # 最后一个节点下方多算了一个间距，减去
        if first_idx is not None and total_h > 0:
            for back in self._order_list[first_idx:]:
                node_item = self._item_map[back]
                for cid in self._canvas_ids(node_item):
                    self._box.move(cid, 0, -total_h)

        # 修正父节点
        parent = item.parent() if item.parent is not None else None
        if parent is not None:
            parent.children = [c for c in parent.children if c is not item]
            if not parent.children:
                self._demote_to_leaf(parent)
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
    
    def bind(self, sequence=None, func=None, add=None):
        """绑定事件，代理给画布实现"""
        return self._box.bind(sequence, func, add)
    
    def unbind(self, sequence, funcid=None):
        """解绑事件，代理给画布实现"""
        self._box.unbind(sequence, funcid)
    
    def check_change(self, item: TinUITreeItem, state=None):
        """外部接口：切换节点选中状态，支持 True/False/2('half')/None(取反)"""
        self._check_change(item, state)

    # ====================
    # 初始化加载
    # ====================

    def _load_content(self, content, parent: TinUITreeItem|None = None, padx=5):
        """递归解析原始 content 格式并构建节点树"""
        children: list[TinUITreeItem] = []
        for text in content:
            if isinstance(text, str):
                item = self._create_leaf(text, padx, parent, insert_after=None)
            else:
                # (label, (child1, child2, ...))
                item = self._create_branch(text[0], padx, parent, insert_after=None)
                self._load_content(text[1], item, padx + self.scale_value(15))
                # 折叠图标绑定
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

    def _calc_insert_y(self, insert_after: TinUITreeItem|None) -> int:
        """
        计算新节点应绘制的 Y 坐标。
          insert_after=None -> 追加到画布末尾: _endy()
          insert_after=node -> 插入到该节点 bbox 底部的正下方，
                               同时将该节点之后的所有现有节点向下移动一行
        返回 (y, insert_index)：Y坐标，在 _order_list 中的插入位置索引
        """
        if insert_after is None:
            return self._endy() + self.scale_value(3), len(self._order_list)

        bbox = self._box.bbox(insert_after.back)
        if bbox is None:
            return self._endy() + self.scale_value(3), len(self._order_list)

        insert_y = bbox[3] + self.scale_value(3)          # 紧接在 insert_after 下方
        row_h    = bbox[3] - bbox[1] - self.scale_value(1) # 预估新节点高度与 insert_after 同高

        # 找到 insert_after 在 _order_list 中的索引，新节点插入其后
        insert_index = self._order_list.index(insert_after.back) + 1

        # 把该位置之后的所有节点向下移动一行
        for back in self._order_list[insert_index:]:
            node = self._item_map[back]
            for cid in self._canvas_ids(node):
                self._box.move(cid, 0, row_h)

        return insert_y, insert_index

    def _insert_into_map(self, back, item: TinUITreeItem, insert_index: int):
        """在 _item_map 的指定位置插入新条目（保持有序）"""
        self._item_map[back] = item
        self._order_list.insert(insert_index, back)

    def _create_leaf(self, text: str, padx: int, parent,
                     checkable: bool = False, check_state: bool = False,
                     insert_after: TinUITreeItem|None = None) -> TinUITreeItem:
        y, insert_index = self._calc_insert_y(insert_after)
        te = self._box.create_text(
            (padx + self.scale_value(15), y), text=text,
            font=self._font, fill=self._fg, tags="item", anchor="nw",
        )
        back = self._box.add_back((), (te,), fg=self._bg, bg=self._bg)
        item = TinUITreeItem(text, back, te, sign=None, parent=parent)
        self._insert_into_map(back, item, insert_index)
        if checkable:
            self._add_check(item, checkable, check_state)
        return item

    def _create_branch(self, text: str, padx: int, parent,
                       insert_after: TinUITreeItem|None = None) -> TinUITreeItem:
        y, insert_index = self._calc_insert_y(insert_after)
        sign = self._box.create_text(
            (padx - self.scale_value(1), y + self.scale_value(3)), text=self._ICON_OPEN,
            font=self._icon_font,
            fill=self._signcolor, anchor="nw",
        )
        signx = self._box.bbox(sign)[2]
        te = self._box.create_text(
            (signx, y), text=text,
            font=self._font, fill=self._fg, tags="item", anchor="nw",
        )
        back = self._box.add_back((), (sign, te), fg=self._bg, bg=self._bg)
        item = TinUITreeItem(text, back, te, sign=sign, parent=parent)
        self._insert_into_map(back, item, insert_index)
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
        index = self._order_list.index(last_leaf_back) + 1
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
        index = self._order_list.index(last_desc_back) + 1
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
        self._box.moveto(self._line, -self.scale_value(1), posi[1] + self._linew / 5)
        if self._command is not None and send:
            path = []
            node = item
            while node is not None:
                path.append(node)
                node = node.parent() if node.parent is not None else None
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
            node = node.parent() if node.parent is not None else None
        return 5 + depth * self.scale_value(15)

    def _canvas_ids(self, item: TinUITreeItem):
        """返回节点关联的所有画布 id（背景、文字、图标）"""
        ids = [item.back, item.te, *(item.checkitems if item.checkable else ())]
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

    def _get_last_node(self, item: TinUITreeItem) -> TinUITreeItem:
        """获取以 item 为根的子树中最后一个后代节点，用于确定插入锚点"""
        desc = self._collect_descendants(item)
        return desc[-1] if desc else item

    def _move_index(self, index: int, dy: int):
        """将 item_map 中第 index 个之后的所有节点整体移动 dy"""
        for back in self._order_list[index:]:
            node = self._item_map[back]
            for cid in self._canvas_ids(node):
                self._box.move(cid, 0, dy)

    def _fix_back_width(self, back):
        """调整背景矩形宽度以填满视口"""
        old_coords = self._box.coords(back)
        old_coords[0] = old_coords[6] = self.scale_value(6)
        bbox = self._box.bbox(back)
        if bbox and bbox[2] - bbox[0] < self._width:
            old_coords[2] = old_coords[4] = self._width - self._master.TINUI_RADIUS_SMALL
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
        padx = self._calc_padx(parent.parent() if parent.parent is not None else None)  # 图标在文字左侧
        y = te_coords[1] + self.scale_value(3)
        sign = self._box.create_text(
            (padx - self.scale_value(1), y), text=self._ICON_OPEN,
            font=self._icon_font,
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
    
    def _add_check(self, item: TinUITreeItem, checkable: bool, check_state: bool):
        """为节点添加可选状态"""
        item.checkable = checkable
        item.check_state = self._normalize_check_state(check_state)
        checkoutl = self._box.create_text(
            (0, 0), text=self._ICON_CHECKOUTL,
            font=self._icon_font, fill=self._signcolor,
        )
        checkfill = self._box.create_text(
            (0, 0), text=self._ICON_CHECKFILL,
            font=self._icon_font, fill="",
        )
        checktext = self._box.create_text(
            (0, 0), text=self._ICON_CHECKTICK,
            font=self._icon_font, fill="",
        )
        item.checkitems = (checkoutl, checkfill, checktext)
        bbox = self._box.bbox(item.te)
        pos = (bbox[0] + self._icon_width / 2 + self.scale_value(1), (bbox[1] + bbox[3]) / 2)
        self._box.coords(checkoutl, pos)
        self._box.coords(checkfill, pos)
        self._box.coords(checktext, pos)
        self._apply_check_visual(item)
        self._box.move(item.te, self._icon_width + self.scale_value(2), 0)
        for cid in item.checkitems:
            self._box.tag_bind(cid, "<Button-1>", lambda _: self._check_change(item))

    def _normalize_check_state(self, state) -> int:
        """规范化状态：0=未选，1=全选，2=半选。"""
        if state in (2, "half", "partial"):
            return 2
        if state in (True, 1, "checked"):
            return 1
        return 0

    def _apply_check_visual(self, item: TinUITreeItem):
        """按三态刷新节点勾选图标。"""
        state = item.check_state
        if state == 1:
            line_color = ""
            fill_color = self._oncolor
            text = self._ICON_CHECKTICK
            text_color = self._bg
        elif state == 2:
            line_color = ""
            fill_color = self._oncolor
            text = self._ICON_CHECKHALF
            text_color = self._bg
        else:
            line_color = self._signcolor
            fill_color = ""
            text = ""
            text_color = ""
        self._box.itemconfig(item.checkitems[0], fill=line_color)
        self._box.itemconfig(item.checkitems[1], fill=fill_color)
        self._box.itemconfig(item.checkitems[2], fill=text_color, text=text)

    def _check_change(self, item: TinUITreeItem, state=None, need_update_parent=True):
        """切换节点选中状态（三态），并按需同步子孙与父级状态。"""
        if not item.checkable:
            return

        if state is None:
            # 交互切换：半选视为未完成，下一次切到全选
            item.check_state = 0 if item.check_state == 1 else 1
        else:
            item.check_state = self._normalize_check_state(state)

        self._apply_check_visual(item)

        # 级联更新子节点状态：仅全选/未选向下传播，半选由子节点聚合得出
        if item.check_state in (0, 1):
            for child in item.children:
                if child.checkable:
                    self._check_change(child, state=item.check_state, need_update_parent=False)

        # 向上传递
        if not need_update_parent:
            return
        parent = item.parent() if item.parent is not None else None
        while parent is not None:
            if parent.checkable:
                child_states = [c.check_state for c in parent.children if c.checkable]
                if child_states:
                    if all(s == 1 for s in child_states):
                        parent.check_state = 1
                    elif any(s != 0 for s in child_states):
                        parent.check_state = 2
                    else:
                        parent.check_state = 0
                    self._apply_check_visual(parent)
            parent = parent.parent() if parent and parent.parent is not None else None

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
            self._master.itemconfig(self._cavui, height=self._height - self.scale_value(8))
            self._master.itemconfig(self._vscroll, state="normal")
        if bbox[3] - bbox[1] <= self._height:
            self._master.itemconfig(self._cavui, width=self._width)
            self._master.itemconfig(self._hscroll, state="hidden")
        else:
            self._master.itemconfig(self._cavui, width=self._width - self.scale_value(8))
            self._master.itemconfig(self._hscroll, state="normal")
        self._box.config(scrollregion=bbox)

    def _repaintback(self):
        bbox = self._box.bbox("item")
        if bbox is None:
            return
        widgetwidth = max(self._width, bbox[2]) - self._master.TINUI_RADIUS_SMALL
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
            width2  = x2 - x1 - self.scale_value(9)
            dw = width2 - self._width
            self._width = width2
            height2 = y2 - y1 - self.scale_value(9)
            dh = height2 - self._height
            self._height = height2
            master.move(self._hscroll, dw, 0)
            self._hscroll.move(dx + dw, dy, self._height)
            master.move(self._vscroll, 0, dh)
            self._vscroll.move(dx, dy + dh, self._width)
            if self._allback is not None:
                coord = master.coords(self._allback)
                coord[2] = coord[4] = x2 - self.scale_value(4)
                coord[5] = coord[7] = y2 - self.scale_value(4)
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
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(2)  # DPI感知，解决高DPI显示模糊问题
    factor = windll.shcore.GetScaleFactorForDevice(0) / 100
    def test(path: list[TinUITreeItem]):
        print("选中路径:", " > ".join(n.text for n in path))

    root = tk.Tk()
    tinui = BasicTinUI(root)
    tinui.set_scale(factor)
    tinui.pack(fill='both',expand=True)
    tree = TinUITreeView(tinui, (50, 50), command=test, **tvdark)

    # 增
    new_item = tree.add_node("新节点", checkable=True) # 添加到根
    child = tree.add_node("子节点", parent=new_item)  # 添加到指定节点下
    for i in range(5):
        tree.add_node(f"子节点{i}", parent=child)

    two = tree._roots[1]  # 获取第二个根节点 "two"
    for i in range(3):
        tree.add_node(f"two的子{i}", parent=two)
    three = tree._roots[2]  # 获取第三个根节点 "three"
    tree.add_node("three的子", parent=three)
    
    # 删
    tree.remove_node(three.children[2]) # 同时删除所有后代，父节点若变为空则自动降级为叶节点
    
    # 改
    tree.rename_node(new_item, "renamed")
    
    # 查
    # selected = tree.get_selected() # 返回 TinUITreeItem 或 None
    # print("当前选中:", selected)
    
    # 展开/折叠
    tree.close_all()
    tree.select_node(["three", "b", "b1"]) # 根据路径选择节点，自动展开父节点
    # root.after(2000, tree.open_all) # 2秒后展开所有节点

    rp = ExpandPanel(tinui, tree.uid, (10,10,10,10))
    def on_resize(e):
        rp.update_layout(5, 5, e.width-5, e.height-5)
    tinui.bind("<Configure>", on_resize)

    root.mainloop()