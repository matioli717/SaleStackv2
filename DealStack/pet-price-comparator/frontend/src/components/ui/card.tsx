"use client";
export default function Card({children, ...props}: any) { return <div {...props}>{children}</div>; }
export const CardContent = (props: any) => <div {...props} />;
