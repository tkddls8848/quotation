//! 파이썬이 lxml 노드에서 쓰는 만큼만 담는 최소 문서 나무.
//!
//! `find`/`findall` 의 뜻을 그대로 옮기려고 둔다. 이름공간이 붙은 원소는
//! 파이썬 `find()` 와 같이 **찾지 않는다.**
//!
//! - 외부 참조를 하지 않는다. 인라인 DTD 는 읽되 문서가 정의한 엔티티는
//!   펼치지 않는다 (XXE 차단). 규격이 정한 엔티티(`&amp;` 등)와 숫자 참조는
//!   lxml 과 같이 펼친다.
//! - 인코딩은 XML 선언을 따른다 (`quick-xml` 의 `encoding` 기능, `encoding_rs`).

use quick_xml::NsReader;
use quick_xml::events::{BytesRef, Event};
use quick_xml::name::ResolveResult;

use crate::text;

/// 파싱한 원소 하나.
#[derive(Debug, Default)]
pub struct Element {
    /// 접두사를 뗀 이름.
    pub name: String,
    /// 이름공간이 붙어 있는가. 붙어 있으면 파이썬 `find()` 가 찾지 못한다.
    pub namespaced: bool,
    /// 첫 자식(또는 펼치지 않은 엔티티) 앞까지의 글. lxml `.text` 와 같다.
    pub text: String,
    /// 글 모으기를 끝냈는가.
    closed_text: bool,
    pub children: Vec<Element>,
}

impl Element {
    /// 파이썬 `el.find(path)` — 이름공간 없는 자식만 따라간다.
    pub fn find(&self, path: &[&str]) -> Option<&Element> {
        let mut node = self;
        for step in path {
            node = node
                .children
                .iter()
                .find(|child| !child.namespaced && child.name == *step)?;
        }
        Some(node)
    }

    /// 파이썬 `el.findall("./name")`.
    pub fn children_named<'a>(&'a self, name: &'a str) -> impl Iterator<Item = &'a Element> {
        self.children
            .iter()
            .filter(move |child| !child.namespaced && child.name == name)
    }

    /// 파이썬 `el.findall(".//name")` — 문서 순서로 모든 자손.
    pub fn descendants_named<'a>(&'a self, name: &'a str, found: &mut Vec<&'a Element>) {
        for child in &self.children {
            if !child.namespaced && child.name == name {
                found.push(child);
            }
            child.descendants_named(name, found);
        }
    }

    /// 파이썬 `el.iter()` — 자기 자신부터 모든 자손.
    pub fn iter(&self) -> impl Iterator<Item = &Element> {
        let mut stack = vec![self];
        std::iter::from_fn(move || {
            let node = stack.pop()?;
            stack.extend(node.children.iter().rev());
            Some(node)
        })
    }

    /// 파이썬 `_text` — 없으면 빈 글, 있으면 앞뒤를 다듬는다.
    pub fn text_at(&self, path: &[&str]) -> &str {
        self.find(path).map_or("", |node| text::strip(&node.text))
    }
}

/// 바이트 -> 원소 나무. 실패하면 사람이 읽을 수 있는 까닭을 돌려준다.
pub fn parse(data: &[u8]) -> Result<Element, String> {
    let mut reader = NsReader::from_reader(data);
    reader.config_mut().check_end_names = true;
    let mut buffer = Vec::new();
    let mut stack: Vec<Element> = Vec::new();
    let mut root: Option<Element> = None;

    loop {
        let (namespace, event) = reader
            .read_resolved_event_into(&mut buffer)
            .map_err(|error| error.to_string())?;
        match event {
            Event::Start(tag) => {
                let element = open(tag.name().local_name().as_ref(), &namespace);
                mark_child(&mut stack);
                stack.push(element);
            }
            Event::Empty(tag) => {
                let element = open(tag.name().local_name().as_ref(), &namespace);
                mark_child(&mut stack);
                close(&mut stack, &mut root, element)?;
            }
            Event::End(_) => {
                let element = stack.pop().ok_or("닫는 태그가 남습니다.")?;
                close(&mut stack, &mut root, element)?;
            }
            Event::Text(body) => {
                let decoded = body
                    .decode()
                    .map_err(|error| error.to_string())?
                    .into_owned();
                push_text(&mut stack, &decoded);
            }
            Event::CData(body) => {
                // CDATA 도 lxml 에서는 그냥 글이다.
                let decoded = reader
                    .decoder()
                    .decode(&body)
                    .map_err(|error| error.to_string())?
                    .into_owned();
                push_text(&mut stack, &decoded);
            }
            // 규격이 정한 엔티티와 숫자 참조는 lxml 과 같이 펼친다. 문서가 스스로
            // 정의한 엔티티만 펼치지 않고, 거기서 `.text` 가 끝난다 (XXE 차단).
            Event::GeneralRef(reference) => match predefined(&reference) {
                Some(character) => push_text(&mut stack, &character.to_string()),
                None => mark_child(&mut stack),
            },
            Event::Eof => break,
            _ => {}
        }
        buffer.clear();
    }

    if !stack.is_empty() {
        return Err("닫히지 않은 태그가 있습니다.".to_owned());
    }
    root.ok_or_else(|| "빈 화일입니다.".to_owned())
}

fn open(name: &[u8], namespace: &ResolveResult) -> Element {
    Element {
        name: String::from_utf8_lossy(name).into_owned(),
        namespaced: matches!(namespace, ResolveResult::Bound(_)),
        ..Element::default()
    }
}

/// 규격이 정한 엔티티(`&amp;` 등)와 숫자 참조를 글자로 바꾼다.
///
/// 문서가 `<!ENTITY ...>` 로 정의한 것은 여기서 `None` 이 되어 펼쳐지지 않는다.
fn predefined(reference: &BytesRef<'_>) -> Option<char> {
    if let Ok(Some(character)) = reference.resolve_char_ref() {
        return Some(character);
    }
    match reference.as_ref() {
        b"amp" => Some('&'),
        b"lt" => Some('<'),
        b"gt" => Some('>'),
        b"quot" => Some('"'),
        b"apos" => Some('\''),
        _ => None,
    }
}

/// 첫 자식 앞까지의 글만 모은다.
fn push_text(stack: &mut [Element], body: &str) {
    if let Some(current) = stack.last_mut() {
        if !current.closed_text {
            current.text.push_str(body);
        }
    }
}

/// 자식이 하나라도 생기면 그 원소의 `.text` 는 더 자라지 않는다 (lxml 과 같다).
fn mark_child(stack: &mut [Element]) {
    if let Some(current) = stack.last_mut() {
        current.closed_text = true;
    }
}

fn close(
    stack: &mut [Element],
    root: &mut Option<Element>,
    element: Element,
) -> Result<(), String> {
    match stack.last_mut() {
        Some(parent) => parent.children.push(element),
        None => {
            if root.is_some() {
                return Err("뿌리 원소가 둘입니다.".to_owned());
            }
            *root = Some(element);
        }
    }
    Ok(())
}
