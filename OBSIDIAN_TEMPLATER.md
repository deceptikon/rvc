<%*
const title = await tp.system.prompt("Issue Title");
const type = await tp.system.suggester(["story", "bug", "task", "epic"], ["story", "bug", "task", "epic"]);
const priority = await tp.system.suggester(["Low", "Medium", "High", "Critical"], ["Low", "Medium", "High", "Critical"]);
const id = "ISSUE-" + Math.floor(Math.random() * 1000); // Or use a sequence
const date = tp.date.now("YYYY-MM-DD");

const fileName = `${id}-${title.replace(/\s+/g, '-')}`;
await tp.file.rename(fileName);

const content = `---
id: ${id}
type: ${type}
status: To Do
priority: ${priority}
assignee: "@human"
created: ${date}
tags: []
---
# ${title}

## Description
Enter description here...

## Tasks
- [ ] 
`;

tR += content;
%>
